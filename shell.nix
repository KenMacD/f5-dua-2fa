{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    yubikey-manager
    pass
    ocproxy
    (python3.withPackages(ps: with ps; [
      # Run
      requests
      pexpect

      # Build
      black
    ]))
  ];
}
