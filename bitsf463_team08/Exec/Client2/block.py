from datetime import datetime
import os
import hashlib
import json
from twisted.internet import reactor

from pymerkle import MerkleTree

"""This file contains the implementation of the classes for handling Blocks and the Blockchain"""

class Block:
    """This class defines the structure of a block"""
    def __init__(self, prev_hash : str, transactions : list) -> None:
        """Initializes a block object"""

        # Add the current system time to the block
        timestamp = str(datetime.now())

        # Generate the merkle root for all the transactions in the block
        merkle_root = self.get_root(transactions.copy())

        # Store the details associated with the block
        self.details = {
            "header" : {
                "prev_hash" : prev_hash,
                "timestamp" : timestamp,
                "merkle_root" : merkle_root
            },
            "body" : {
                "transactions" : transactions
            }
        }

    def get_hash(self) -> str:
        """Function to calculate the SHA256 hash of the block header"""

        return hashlib.sha256((self.details["header"]["prev_hash"] + 
        self.details["header"]["timestamp"] + 
        self.details["header"]["merkle_root"]).encode()).hexdigest()

    def get_root(self, transactions : list) -> str:
        """Function to calculate the merkle root of the transactions"""

        # No merkle root for genesis block
        if len(transactions) == 0:
            return "None"

        # Keep hashing till only 1 value is remaining
        while len(transactions) != 1:
            # If number of leaf nodes is odd, make it even
            if len(transactions) % 2 != 0:
                transactions.append(transactions[-1])

            processed = []
            string = ""
            
            # Hash pairwise
            for id in transactions:
                if string == "":
                    string += id
                    continue
                string += id
                processed.append(hashlib.sha256(string.encode()).hexdigest())
                string = ""
            transactions = processed.copy()

        return transactions[0]

class BlockChain:
    """This class defines the structure of the blockchain"""

    def __init__(self) -> None:
        """Initializes the blockchain object"""

        # Check if data of a blockchain already exists
        # Else create a new blockchain instance
        if os.path.exists("./data/blockchain.txt"):
            with open("./data/blockchain.txt", 'r') as f:
                self.head = f.read()

            with open("./data/block_list.txt", 'r') as f:
                self.block_list = json.loads(f.read())
        else:
            genesis_block = Block("", [])
            self.head = genesis_block.get_hash()

            with open("./data/blockchain.txt", 'w') as f:
                f.write(self.head)

            self.block_list = {}
            self.block_list[genesis_block.get_hash()] = genesis_block.details

            with open("./data/block_list.txt", 'w') as f:
                f.write(json.dumps(self.block_list))

    def transfer_data(self, client, data : bytes, addr : tuple) -> None:
        """Thread-safe method to send data to peers over UDP protocol"""
        client.transport.write(data, addr)


    def add_block(self, new_block : Block) -> None:
        """Function to add a new block into the blockchain"""
        self.head = new_block.get_hash()

        with open("./data/blockchain.txt", 'w') as f:
            f.write(self.head)

        self.block_list[new_block.get_hash()] = new_block.details

        with open("./data/block_list.txt", 'w') as f:
            f.write(json.dumps(self.block_list))

        print("Minting Complete!\n")

    def mint_block(self, peer_list : dict, client) -> None:
        """Function to mint a new block and propagate it across the network"""

        # Load the data of the new transactions
        new_transactions = {}
        with open("./data/temp_transactions.txt", 'r') as f:
            new_transactions = json.loads(f.read())

        new_properties = {}
        with open("./data/temp_properties.txt", 'r') as f:
            new_properties = json.loads(f.read())

        if os.path.exists("./data/properties.txt"):
            with open("./data/properties.txt", 'r') as f:
                existing_properties = json.loads(f.read())
        else:
            existing_properties = {}

        if os.path.exists("./data/transactions.txt"):
            with open("./data/transactions.txt", 'r') as f:
                existing_transactions = json.loads(f.read())
        else:
            existing_transactions = {}

        # Create the new block to be added
        new_block = Block(self.head, [id for id in new_transactions])

        # Process the transactions
        for transaction_id in new_transactions:
            if new_transactions[transaction_id]["seller_id"] == "NA":
                peer_list[new_transactions[transaction_id]["buyer_id"]]["properties"].append(new_transactions[transaction_id]["property_id"])
                new_properties[new_transactions[transaction_id]["property_id"]]["history"].insert(0, transaction_id)
            else:
                peer_list[new_transactions[transaction_id]["buyer_id"]]["properties"].append(new_transactions[transaction_id]["property_id"])
                peer_list[new_transactions[transaction_id]["seller_id"]]["properties"].remove(new_transactions[transaction_id]["property_id"])
                existing_properties[new_transactions[transaction_id]["property_id"]]["history"].insert(0, transaction_id)
               

        # Merge the previously completed and currently completed transactions
        existing_transactions = existing_transactions | new_transactions
        existing_properties = existing_properties | new_properties

        new_transactions = {}
        new_properties = {}

        # Check to see if new block was received
        with open("./data/blockchain.txt", 'r') as f:
            self.head = f.read()

        with open("./data/block_list.txt", 'r') as f:
            self.block_list = json.loads(f.read())

        # Storing all the modified data

        with open("./data/temp_transactions.txt", 'w') as f:
            f.write(json.dumps(new_transactions))
        
        with open("./data/temp_properties.txt", 'w') as f:
            f.write(json.dumps(new_properties))

        with open("./data/properties.txt", 'w') as f:
            f.write(json.dumps(existing_properties))
        
        with open("./data/transactions.txt", 'w') as f:
            f.write(json.dumps(existing_transactions))

        with open("./data/peer_list.txt", 'w') as f:
            f.write(json.dumps(peer_list))

        # Check to see if new block was received
        if self.head != new_block.details["header"]["prev_hash"]:
            print("Minting Stopped!\n")
            return
        
        # Add minted block to chain
        self.add_block(new_block)

        # Send the new block to the peers
        data = {
            "tag" : "new_block",
            "data" : [self.block_list, self.head]
        }

        data = json.dumps(data)
        data = data.encode("utf-8")
        
        for peer in peer_list:
            if peer == client.id:
                continue

            reactor.callFromThread(self.transfer_data, client, data, ("127.0.0.1", peer_list[peer]["port_no"]))

if __name__ == "__main__":
    chain = BlockChain()