from uuid import uuid4
from random import randint
import os
import json
import pickle
import random
import math
import time

from block import Block, BlockChain
from property import Property
from transaction import Transaction

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor

"""This file contains the implementation of the Client class"""
def find_key(string):
    index = 0
    for char in string:
        if not char.isdigit():
            break
        index += 1

    return int(string[:index])

class Client(DatagramProtocol):
    """This class defines the structure and actions of a client"""
    def __init__(self, port : int, first_client : bool = False) -> None:
        """Initializes the Client object"""
        self.properties = {}
        # Check to see if ID already exists
        # Else generate a new ID
        if os.path.exists("./data/id.txt"):
            with open("./data/id.txt", 'r') as f:
                data = f.read()
                self.id = data.split('#')[0]
                self.port_no = int(data.split('#')[1])
        else:
            self.id = str(uuid4())
            self.port_no = port
            os.mkdir("data")
            with open("./data/id.txt", 'w') as f:
                f.write(self.id + '#' + str(port))

        self.first_client = first_client
        self.peer_list = {}

    def startProtocol(self) -> None:
        """Function runs after the client is initialized"""

        sleep_time = 2

        # Create a new peer list if first client
        # Else get the updated peer list from other peers / first client
        if not self.first_client:
            if os.path.exists("./data/peer_list.txt"):
                with open("./data/peer_list.txt", 'r') as f:
                    self.peer_list = json.loads(f.read())

                data = {
                    "tag" : "request_update",
                    "data" : ""
                }

                data = json.dumps(data)
                data = data.encode("utf-8")

                for peer in self.peer_list:
                    if peer == self.id:
                        continue

                    reactor.callFromThread(self.transfer_data, data, ("127.0.0.1", self.peer_list[peer]["port_no"]))
                    sleep_time = 5
            else:
                data = {
                    "tag" : "new_user",
                    "data" : [self.id, self.port_no]
                }
                data = json.dumps(data)
                data = data.encode("utf-8")
                reactor.callFromThread(self.transfer_data, data, ("127.0.0.1", 1000))
        else:
            self.peer_list[self.id] = {
                "port_no" : self.port_no,
                "properties" : []
            }

            with open("./data/peer_list.txt", 'w') as f:
                f.write(json.dumps(self.peer_list))

        time.sleep(sleep_time)
        self.chain = BlockChain()

        # Start the event loop
        reactor.callInThread(self.event_loop)

    def create_proof(self, transaction):
        prop_id = list(transaction.values())[0]["property_id"]
        prop = self.properties.get(prop_id)
        if(prop is None):
            self.valid_transaction=False
            self.feedback_received=True
            return

        prop.generate_h()

        data = {
                "tag" : "sending_transaction_with_h",
                "data" : [transaction, prop.h, self.port_no, prop.public_key, prop.p, prop.g]
                }
        data = json.dumps(data)
        data = data.encode("utf-8")
        for peer in self.peer_list:
            if peer == self.id:
                continue
            time.sleep(0.15)
            reactor.callFromThread(self.transfer_data, data, ("127.0.0.1", self.peer_list[peer]["port_no"]))

        return

    def datagramReceived(self, datagram: bytes, addr : tuple) -> None:
        """Function runs when a datagram is received"""

        datagram = datagram.decode("utf-8")
        datagram = json.loads(datagram)

        # Update the list of pending properties to be added
        if datagram["tag"] == "temp_properties":
            with open("./data/temp_properties.txt", 'w') as f:
                f.write(json.dumps(datagram["data"]))

        # Update the list of pending transactions to be added
        elif datagram["tag"] == "temp_transactions":
            with open("./data/temp_transactions.txt", 'w') as f:
                f.write(json.dumps(datagram["data"]))

            # If the number of pending transactions is 3, start minting the block
            if len(datagram["data"]) == 3:
                reactor.callInThread(self.proof_oet)

        # Request from a new user processed - Send all data
        elif datagram["tag"] == "new_user":
            self.peer_list[datagram["data"][0]] = {
                "port_no" : datagram["data"][1],
                "properties" : []
            }

            with open("./data/peer_list.txt", 'w') as f:
                f.write(json.dumps(self.peer_list))

            data = {
                "tag" : "peer_list_update",
                "data" : self.peer_list
            }
            data = json.dumps(data)
            data = data.encode("utf-8")

            for peer in self.peer_list:
                if peer == self.id:
                    continue
                reactor.callFromThread(self.transfer_data, data, ("127.0.0.1", self.peer_list[peer]["port_no"]))

            block_list = {}
            blockchain = {}
            temp_transactions = {}
            temp_properties = {}
            transactions = {}
            properties = {}

            if os.path.exists("./data/block_list.txt"):
                with open("./data/block_list.txt", 'r') as f:
                    block_list = json.loads(f.read())

            if os.path.exists("./data/blockchain.txt"):
                with open("./data/blockchain.txt", 'r') as f:
                    blockchain = f.read()

            if os.path.exists("./data/temp_transactions.txt"):
                with open("./data/temp_transactions.txt", 'r') as f:
                    temp_transactions = json.loads(f.read())

            if os.path.exists("./data/temp_properties.txt"):
                with open("./data/temp_properties.txt", 'r') as f:
                    temp_properties = json.loads(f.read())

            if os.path.exists("./data/transactions.txt"):
                with open("./data/transactions.txt", 'r') as f:
                    transactions = json.loads(f.read())

            if os.path.exists("./data/properties.txt"):
                with open("./data/properties.txt", 'r') as f:
                    properties = json.loads(f.read())

            data = {
                "tag" : "new_user_response",
                "data" : [block_list, blockchain, temp_transactions, temp_properties, transactions, properties]
            }

            data = json.dumps(data)
            data = data.encode("utf-8")

            reactor.callFromThread(self.transfer_data, data, addr)

        # Response received by the new user
        elif datagram["tag"] == "new_user_response":
            list_dict = datagram["data"]
            with open("./data/block_list.txt", 'w') as f:
                f.write(json.dumps(list_dict[0]))

            self.chain.block_list = list_dict[0]

            with open("./data/blockchain.txt", 'w') as f:
                f.write(list_dict[1])

            self.chain.head = list_dict[1]

            with open("./data/temp_transactions.txt", 'w') as f:
                f.write(json.dumps(list_dict[2]))

            with open("./data/temp_properties.txt", 'w') as f:
                f.write(json.dumps(list_dict[3]))

            with open("./data/transactions.txt", 'w') as f:
                f.write(json.dumps(list_dict[4]))

            with open("./data/properties.txt", 'w') as f:
                f.write(json.dumps(list_dict[5]))

        # Update the peer list after a new user joins
        elif datagram["tag"] == "peer_list_update":
            self.peer_list = datagram["data"]
            with open("./data/peer_list.txt", 'w') as f:
                f.write(json.dumps(self.peer_list))

        # Receives the new block from the winner of the mint
        elif datagram["tag"] == "new_block":
            list_dict = datagram["data"]

            with open("./data/block_list.txt", 'w') as f:
                f.write(json.dumps(list_dict[0]))

            with open("./data/blockchain.txt", 'w') as f:
                f.write(list_dict[1])

        # Request an update after logging back onto the network
        elif datagram["tag"] == "request_update":
            data = {
                "tag" : "peer_list_update",
                "data" : self.peer_list
            }

            data = json.dumps(data)
            data = data.encode("utf-8")

            reactor.callFromThread(self.transfer_data, data, addr)

            block_list = {}
            blockchain = {}
            temp_transactions = {}
            temp_properties = {}
            transactions = {}
            properties = {}

            if os.path.exists("./data/block_list.txt"):
                with open("./data/block_list.txt", 'r') as f:
                    block_list = json.loads(f.read())

            if os.path.exists("./data/blockchain.txt"):
                with open("./data/blockchain.txt", 'r') as f:
                    blockchain = f.read()

            if os.path.exists("./data/temp_transactions.txt"):
                with open("./data/temp_transactions.txt", 'r') as f:
                    temp_transactions = json.loads(f.read())

            if os.path.exists("./data/temp_properties.txt"):
                with open("./data/temp_properties.txt", 'r') as f:
                    temp_properties = json.loads(f.read())

            if os.path.exists("./data/transactions.txt"):
                with open("./data/transactions.txt", 'r') as f:
                    transactions = json.loads(f.read())

            if os.path.exists("./data/properties.txt"):
                with open("./data/properties.txt", 'r') as f:
                    properties = json.loads(f.read())

            data = {
                "tag" : "new_user_response",
                "data" : [block_list, blockchain, temp_transactions, temp_properties, transactions, properties]
            }

            data = json.dumps(data)
            data = data.encode("utf-8")

            reactor.callFromThread(self.transfer_data, data, addr)

        elif datagram["tag"]=="sending_transaction_with_h":
            self.h = datagram["data"][1]
            self.b = random.randint(0,1)
            self.public_key = find_key(list(datagram["data"][0].values())[0]["property_id"])
            self.p = datagram["data"][4]
            self.g = datagram["data"][5]
            data = {
            "tag" : "sending_transaction_with_b",
            "data" : [datagram["data"][0], self.b, self.port_no]
            }
            data = json.dumps(data)
            data = data.encode("utf-8")
            reactor.callFromThread(self.transfer_data, data, ("127.0.0.1", datagram["data"][2]))


        elif datagram["tag"]=="sending_transaction_with_b":
            prop = self.properties[list(datagram["data"][0].values())[0]["property_id"]]
            prop_json = {}
            prop_json[prop.id] = prop.details
            prop.b = datagram["data"][1]
            prop.generate_s()
            data = {
            "tag" : "sending_transaction_with_s",
            "data" : [datagram["data"][0], prop.s, self.port_no, prop_json]
            }
            data = json.dumps(data)
            data = data.encode("utf-8")
            reactor.callFromThread(self.transfer_data, data, ("127.0.0.1", datagram["data"][2]))

        elif datagram["tag"]=="sending_transaction_with_s":
            self.s = datagram["data"][1]
            result = (pow(self.g,self.s)%self.p == (self.h*pow(self.public_key,self.b))%self.p)
            data = {
            "tag" : "proof_result",
            "data" : [datagram["data"][0], result, self.port_no]
            }
            data = json.dumps(data)
            data = data.encode("utf-8")
            if(result and list(datagram["data"][0].values())[0]["buyer_id"]==self.id):
                # datagram["data"][3][0].generate_keys()
                prop = Property(list(datagram["data"][3].values())[0]["address"], list(datagram["data"][3].values())[0]["history"])
                self.properties[prop.id]=prop
            reactor.callFromThread(self.transfer_data, data, ("127.0.0.1", datagram["data"][2]))

        elif datagram["tag"]=="proof_result":
            if(datagram["data"][1]):
                self.properties.pop(list(datagram["data"][0].values())[0]["property_id"])
                self.valid_transaction=True
            else:
                self.valid_transaction=False

            self.feedback_received=True

    def transfer_data(self, data, addr):
        """Function to transfer data over UDP in a thread-safe manner"""
        self.transport.write(data, addr)

    def event_loop(self):
        """The main event loop"""
        while(True):
            print()
            print("1. Display my details")
            print("2. Add a new property")
            print("3. Sell my property")
            print("4. View my owned properties")
            print("5. View details of a particular property")
            print("6. View details of a particular transaction")
            print("7. View detials of a particular block")
            print("8. View the blockchain")
            print()

            choice = input("Enter your choice (type 'quit' to quit): ")

            if choice == "1":
                print()
                print("UUID:", self.id)
                print("Port:", self.port_no)
                print("Peers:", list(self.peer_list.keys()))
                print()

            elif choice == "2":
                address = input("Enter the address of the property: ")
                new_property = Property(address)
                ## is the dict correct?
                self.properties[new_property.id]=new_property
                new_transaction = Transaction(self.id, "NA", new_property.id, 0.0)

                if os.path.exists("./data/temp_properties.txt"):
                    with open("./data/temp_properties.txt", 'r') as f:
                        temp_properties = json.loads(f.read())
                else:
                    temp_properties = {}

                temp_properties[new_property.id] = new_property.details

                with open("./data/temp_properties.txt", 'w') as f:
                    f.write(json.dumps(temp_properties))

                if os.path.exists("./data/temp_transactions.txt"):
                    with open("./data/temp_transactions.txt", 'r') as f:
                        temp_transactions = json.loads(f.read())
                else:
                    temp_transactions = {}

                temp_transactions[new_transaction.id] = new_transaction.details

                with open("./data/temp_transactions.txt", 'w') as f:
                    f.write(json.dumps(temp_transactions))

                sendable_transactions = {
                    "tag" : "temp_transactions",
                    "data" : temp_transactions
                }

                sendable_properties = {
                    "tag" : "temp_properties",
                    "data" : temp_properties
                }

                sendable_properties = json.dumps(sendable_properties)
                sendable_properties = sendable_properties.encode("utf-8")

                sendable_transactions = json.dumps(sendable_transactions)
                sendable_transactions = sendable_transactions.encode("utf-8")

                for peer in self.peer_list:
                    if peer == self.id:
                        continue
                    time.sleep(0.15)
                    reactor.callFromThread(self.transfer_data, sendable_properties, ("127.0.0.1", self.peer_list[peer]["port_no"]))

                    time.sleep(0.15)
                    reactor.callFromThread(self.transfer_data, sendable_transactions, ("127.0.0.1", self.peer_list[peer]["port_no"]))

                if len(temp_transactions) == 3:
                    reactor.callInThread(self.proof_oet)

            elif choice == "3":
                buyer_id = input("Enter the Buyer ID: ")
                property_id = input("Enter the Property ID: ")
                amount = float(input("Enter the amount: "))

                if buyer_id not in self.peer_list:
                    print("Invaid Buyer ID!")
                    continue
                elif property_id not in self.peer_list[self.id]["properties"]:
                    print("Property not owned!")
                    continue

                new_transaction = Transaction(buyer_id, self.id, property_id, amount)

                if os.path.exists("./data/temp_transactions.txt"):
                    with open("./data/temp_transactions.txt", 'r') as f:
                        temp_transactions = json.loads(f.read())
                else:
                    temp_transactions = {}

                temp_transactions[new_transaction.id] = new_transaction.details

                sendable_transactions = {
                    "tag" : "temp_transactions",
                    "data" : temp_transactions
                }

                sendable_transactions = json.dumps(sendable_transactions)
                sendable_transactions = sendable_transactions.encode("utf-8")

                self.feedback_received = False
                proof_transaction = {}
                proof_transaction[new_transaction.id] = new_transaction.details
                reactor.callInThread(self.create_proof, proof_transaction)
                while(not self.feedback_received):
                    time.sleep(0.1)

                if(self.valid_transaction):
                    with open("./data/temp_transactions.txt", 'w') as f:
                        f.write(json.dumps(temp_transactions))

                    for peer in self.peer_list:
                        if peer == self.id:
                            continue
                        time.sleep(0.1)
                        reactor.callFromThread(self.transfer_data, sendable_transactions, ("127.0.0.1", self.peer_list[peer]["port_no"]))

                        if len(temp_transactions) == 3:
                            reactor.callInThread(self.proof_oet)

            elif choice == '4':
                if os.path.exists("./data/properties.txt"):
                    with open("./data/properties.txt", 'r') as f:
                        properties = json.loads(f.read())
                else:
                    properties = {}

                print()
                for property_id in self.peer_list[self.id]["properties"]:
                    print("Property ID:", property_id)
                    print(properties[property_id])
                    print()

            elif choice == '5':
                property_id = input("Enter the property ID: ")

                if os.path.exists("./data/properties.txt"):
                    with open("./data/properties.txt", 'r') as f:
                        properties = json.loads(f.read())
                else:
                    properties = {}

                print()
                if property_id in properties:
                    print("Property details:\n", properties[property_id])
                else:
                    print("Invalid property ID!")

            elif choice == '6':
                transaction_id = input("Enter the transaction ID: ")

                if os.path.exists("./data/transactions.txt"):
                    with open("./data/transactions.txt", 'r') as f:
                        transactions = json.loads(f.read())
                else:
                    transactions = {}

                print()
                if transaction_id in transactions:
                    print("Transaction details:\n", transactions[transaction_id])
                else:
                    print("Invalid transaction ID!")

            elif choice == '7':
                block_id = input("Enter the block ID: ")

                if os.path.exists("./data/block_list.txt"):
                    with open("./data/block_list.txt", 'r') as f:
                        block_list = json.loads(f.read())
                else:
                    block_list = {}

                print()
                if block_id in block_list:
                    print("Block details:\n", block_list[block_id])
                else:
                    print("Invalid block ID!")

            elif choice == '8':
                if os.path.exists("./data/block_list.txt"):
                    with open("./data/block_list.txt", 'r') as f:
                        block_list = json.loads(f.read())
                else:
                    block_list = {}

                top = self.chain.head
                print(top, end = '')

                top = block_list[top]["header"]["prev_hash"]

                while top != "":
                    print(" ->", top, end = '')
                    top = block_list[top]["header"]["prev_hash"] 

            elif choice == 'quit':
                reactor.callFromThread(reactor.stop)
                break

    def proof_oet(self):
        """Implementation of the Proof of Elapsed Time"""
        sleep_length = random.uniform(0, 15)
        time.sleep(0.5)
        print("\nSleeping for", sleep_length)
        time.sleep(sleep_length)

        self.chain.mint_block(self.peer_list, self)

if __name__ == "__main__":
    port = 1000
    reactor.listenUDP(port, Client(port, True))
    reactor.run()
