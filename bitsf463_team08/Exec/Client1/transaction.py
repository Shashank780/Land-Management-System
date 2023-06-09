import random
import string
from datetime import datetime

"""This file contains the implementation of the Transaction class"""

class Transaction:
    """This class defines the structure of a transaction"""
    def __init__(self, buyer_id : str, seller_id : str, property_id : str, amount : float) -> None:
        """Initializes a transaction object"""

        # Generate an ID for a new transaction
        self.id = ''.join(random.choices(string.ascii_letters, k = 15))

        # Store the details of the transaction
        self.details = {
            "buyer_id" : buyer_id,
            "seller_id" : seller_id,
            "property_id" : property_id,
            "amount" : amount,
            "time" : str(datetime.now())
            }