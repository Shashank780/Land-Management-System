import random
import string

"""This file contains the implementation of the Property class"""

class Property:
    def generate_keys(self):
    # Generate a public/private key pair for the land
        self.p = 761
        self.g = 6
        self.secret_key = random.randint(0, self.p-1)
        self.public_key = pow(self.g, self.secret_key)%self.p
        self.id = str(self.public_key) + self.details["address"]
        return

    """This class defines the structure of a property object"""
    def __init__(self, address, history = []) -> None:
        """Initialzes a property object"""
        # Stores the details of the property
        self.details = {
            "address" : address,
            "history" : history

            }


        # Generate an ID for the new property
        #self.id = ''.join(random.choices(string.ascii_letters, k = 10))
        self.generate_keys()
        self.id = str(self.public_key) + address

    def generate_h(self):
        self.r = random.randint(0 , self.p-1)
        self.h = pow(self.g,self.r)%self.p
        self.b = -1
        return

    def generate_s(self):
        self.s = (self.r + self.b*self.secret_key)%(self.p-1)
        return