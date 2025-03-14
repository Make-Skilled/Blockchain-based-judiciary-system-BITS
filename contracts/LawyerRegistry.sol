// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract LawyerRegistry {
    struct Lawyer {
        string fullName;
        string email;
        string mobileNumber;
        string certificatePath;
        string specialization;
        string experience;  // Changed to string to handle it as text
        string courtType;
        uint8 status;      // 0: pending, 1: accepted, 2: rejected
    }

    mapping(address => Lawyer) public lawyers;
    address[] public lawyerAddresses;
    address public admin;

    event LawyerRegistered(address indexed lawyerAddress, string email);
    event StatusUpdated(address indexed lawyerAddress, uint8 newStatus);

    constructor() {
        admin = msg.sender;
    }

    modifier onlyAdmin() {
        require(msg.sender == admin, "Only admin can perform this action");
        _;
    }

    function registerLawyer(
        string memory _fullName,
        string memory _email,
        string memory _mobileNumber,
        string memory _certificatePath,
        string memory _specialization,
        string memory _experience,
        string memory _courtType
    ) public {
        require(bytes(_fullName).length > 0, "Name cannot be empty");
        require(bytes(_email).length > 0, "Email cannot be empty");
        
        lawyers[msg.sender] = Lawyer({
            fullName: _fullName,
            email: _email,
            mobileNumber: _mobileNumber,
            certificatePath: _certificatePath,
            specialization: _specialization,
            experience: _experience,
            courtType: _courtType,
            status: 0
        });
        
        lawyerAddresses.push(msg.sender);
        emit LawyerRegistered(msg.sender, _email);
    }

    function updateLawyerStatus(address lawyerAddress, uint8 newStatus) public onlyAdmin {
        require(newStatus == 1 || newStatus == 2, "Invalid status");
        lawyers[lawyerAddress].status = newStatus;
        emit StatusUpdated(lawyerAddress, newStatus);
    }

    function getLawyer(address lawyerAddress) public view returns (
        string memory fullName,
        string memory email,
        string memory mobileNumber,
        string memory certificatePath,
        string memory specialization,
        string memory experience,
        string memory courtType,
        uint8 status
    ) {
        Lawyer memory lawyer = lawyers[lawyerAddress];
        return (
            lawyer.fullName,
            lawyer.email,
            lawyer.mobileNumber,
            lawyer.certificatePath,
            lawyer.specialization,
            lawyer.experience,
            lawyer.courtType,
            lawyer.status
        );
    }

    function getAllLawyers() public view returns (address[] memory) {
        return lawyerAddresses;
    }
} 