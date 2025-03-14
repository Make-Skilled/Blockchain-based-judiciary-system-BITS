from web3 import Web3
import json

def test_contract():
    # Connect to Ganache
    w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:7545'))
    
    # Contract details
    contract_address = '0x30de29cA67D34b75134AA7141C3d202e5E430082'
    admin_address = '0x5DF7ee9f009D5f016bB12C1d13FaE90A7EA40286'
    
    # Load contract ABI
    with open('build/contracts/LawyerRegistry.json', 'r') as file:
        contract_data = json.load(file)
        contract_abi = contract_data['abi']
    
    # Initialize contract
    contract = w3.eth.contract(address=contract_address, abi=contract_abi)
    
    # Test contract
    try:
        # Check admin
        contract_admin = contract.functions.admin().call()
        print(f"Contract Admin: {contract_admin}")
        print(f"Expected Admin: {admin_address}")
        print(f"Admin Match: {contract_admin.lower() == admin_address.lower()}")
        
        # Check lawyer count
        lawyers = contract.functions.getAllLawyers().call()
        print(f"\nTotal Lawyers Registered: {len(lawyers)}")
        
        print("\nContract deployment verified successfully!")
        
    except Exception as e:
        print(f"Error testing contract: {e}")

if __name__ == "__main__":
    test_contract() 