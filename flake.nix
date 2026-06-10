{
  description = "crabcc-autoresearch — autonomous ML research loop for λ-term normalization";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
        "x86_64-darwin"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
      pkgsFor = system: nixpkgs.legacyPackages.${system};
    in
    {
      # ── NixOS modules ────────────────────────────────────────────────────────
      # Import one or both in your host configuration:
      #
      #   inputs.crabcc.url = "github:peterlodri-sec/crabcc-autoresearch";
      #   imports = [ inputs.crabcc.nixosModules.research-sync ];
      #
      nixosModules = {
        research-sync = import ./nix/research-sync.nix;
        receiver = import ./nix/receiver.nix;
      };

      # ── Dev shell ─────────────────────────────────────────────────────────────
      # `nix develop` drops you into a shell with all tooling pre-loaded.
      devShells = forAllSystems (
        system:
        let
          pkgs = pkgsFor system;
        in
        {
          default = pkgs.mkShell {
            name = "crabcc-autoresearch";
            packages = with pkgs; [
              uv
              go-task
              git
              gh
            ];
            shellHook = ''
              echo "crabcc-autoresearch dev shell"
              echo "  task run     — launch both autoresearch slots"
              echo "  task test    — run unit tests"
              echo "  task publish — push artifacts to lambda-normalization-census"
            '';
          };
        }
      );

      # ── Formatter ─────────────────────────────────────────────────────────────
      # `nix fmt` formats all .nix files using the RFC-style formatter.
      formatter = forAllSystems (system: (pkgsFor system).nixfmt-rfc-style);

      # ── Checks ────────────────────────────────────────────────────────────────
      # `nix flake check` evaluates modules and builds the dev shell to surface
      # type errors and broken package references early, without CI surprises.
      checks = forAllSystems (
        system:
        let
          pkgs = pkgsFor system;
          lib = nixpkgs.lib;

          # Evaluate a NixOS module config without building the full system.
          # Touching the config attrs in builtins.toJSON forces lazy evaluation
          # (type-checking) without triggering derivation builds.
          evalModule =
            name: module: extraConfig:
            let
              evaled = lib.nixosSystem {
                inherit system;
                modules = [
                  module
                  extraConfig
                  { system.stateVersion = "24.11"; }
                ];
              };
            in
            pkgs.runCommandLocal "check-module-${name}" { } ''
              echo '${
                builtins.toJSON {
                  hasService = evaled.config.systemd.services ? "crabcc-${name}";
                  hasTimer =
                    if name == "research-sync" then
                      evaled.config.systemd.timers ? crabcc-research-sync
                    else
                      true;
                }
              }' > $out
            '';
        in
        {
          # Verify the modules evaluate cleanly (catches option type errors)
          module-research-sync = evalModule "research-sync" self.nixosModules.research-sync {
            services.crabcc.researchSync.enable = true;
          };

          module-receiver = evalModule "receiver" self.nixosModules.receiver {
            services.crabcc.receiver = {
              enable = true;
              repoPath = "/opt/crabcc-autoresearch";
            };
          };

          # Verify the dev shell builds
          devshell = self.devShells.${system}.default;
        }
      );
    };
}
