# JustVerify 0.1.2

New installations now start with incoming Clearnet, Tor and I2P disabled, and outgoing Clearnet, Tor and I2P enabled. This matches the reviewed Umbrel Bitcoin network defaults. Clearnet includes IPv4 and IPv6.

The initial profile saves these selections explicitly. Web and TUI default-reset actions use the same settings and require the existing review/apply flow. Existing saved choices and older implicit network settings are preserved. The internal electrs connection remains available when external incoming connections are disabled.

Fresh I2P router bootstrap no longer blocks Core startup or causes repeated router restarts while reseed servers are unavailable. SAM and peer readiness remain independently checked. Graceful shutdown allows for initial reseed delays so backup/profile changes can retain their normal-stop checks.

The release retains the Tor address announcement correction from 0.1.1. Enabling incoming connections does not guarantee a peer will connect; Clearnet may require router/firewall configuration and privacy networks need working tunnels.

[Network behavior](NETWORKING.md) · [Validation](TESTING.md) · [Installation and recovery](INSTALL.md)
