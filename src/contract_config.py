from web3 import Web3
import json
import os

class ContractConfig:
    def __init__(self):
        self.w3 = None
        self.contract = None
        self.ganache_address = None
        self.initialized = False
        self.initialize()

    def initialize(self):
        try:
            # Connect to Ganache
            self.w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:7545'))
            
            # Get the contract path
            contract_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 
                'build', 
                'contracts', 
                'LawyerRegistry.json'
            )
            
            # Load contract data
            with open(contract_path) as file:
                contract_json = json.load(file)
                contract_abi = contract_json['abi']
                contract_networks = contract_json['networks']
                contract_address = contract_networks['5777']['address']
            
            # Create contract instance
            self.contract = self.w3.eth.contract(address=contract_address, abi=contract_abi)
            
            # Get the first account from Ganache
            self.ganache_address = self.w3.eth.accounts[0]
            
            self.initialized = True
            print(f"Contract loaded successfully at address: {contract_address}")
            print(f"Using Ganache address: {self.ganache_address}")
            print("Available functions:", [func for func in self.contract.all_functions()])
            
        except Exception as e:
            print(f"Error loading contract: {e}")
            self.initialized = False

# Create a single instance
contract_config = ContractConfig()

if contract_config.initialized:
    print(f"Contract loaded successfully at address: {contract_config.ganache_address}")
    print(f"Using Ganache address: {contract_config.ganache_address}")
    print("Available functions:", [func for func in contract_config.contract.all_functions()])
else:
    print("Failed to load contract configuration") 