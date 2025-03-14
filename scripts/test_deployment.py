from web3 import Web3
from contract_config import load_contract_data

def test_contract_deployment():
    # Connect to local blockchain
    w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:7545'))
    
    # Load contract
    contract_abi, contract_address = load_contract_data()
    contract = w3.eth.contract(address=contract_address, abi=contract_abi)
    
    # Test connection
    print(f"Connected to blockchain: {w3.is_connected()}")
    print(f"Contract address: {contract_address}")
    
    # Get admin account
    admin_account = w3.eth.accounts[0]
    print(f"Admin account: {admin_account}")
    
    # Test contract function
    try:
        result = contract.functions.getAllLawyers().call()
        print(f"Current lawyers: {result}")
        print("Contract deployment successful!")
    except Exception as e:
        print(f"Error testing contract: {e}")

if __name__ == "__main__":
    test_contract_deployment() 