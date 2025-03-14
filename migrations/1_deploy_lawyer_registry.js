const LawyerRegistry = artifacts.require("LawyerRegistry");

module.exports = function(deployer) {
  deployer.deploy(LawyerRegistry);
}; 