# SSH administration

From the same local network:

```sh
ssh justverify@justverify.local
```

The initial SSH username and password are both `justverify`. Change the SSH password with `passwd` after first login. The web administrator password is separate.

Starting with **0.1.0-beta2**, this account can administer the OS with `sudo`:

```sh
sudo whoami
```

Enter the **SSH password** at the prompt; the result is `root`. Administrator commands request the password each time. The three fixed application helpers retain their specific passwordless permissions. Web and TUI services continue to run as an ordinary user.

`root` has no default password. The inherited `pi` account is locked, has no login shell and is not an allowed SSH user. Use `justverify` instead. The image generates unique SSH host keys on first boot and preserves a changed password across restarts.

## Existing beta1 installations

Beta1 allowed only the three fixed helpers. A denial from `sudo whoami` on that image is a permission limitation, not an incorrect password. Downloading new source does not change an installed OS.

An existing authorized administrator can install the policy from the verified beta2 source checkout:

```sh
sudo install -o root -g root -m 0440 image/justverify-admin.sudoers /etc/sudoers.d/00-justverify-admin
sudo visudo -c
```

If no administrator account or key is available, shut down through Settings and arrange offline maintenance of the OS partition. Preserve the existing NVMe data partition. Reflashing the whole drive erases the node data and is not required just to correct SSH permissions.
