# NixOS module — systemd service for the crabcc FastAPI telemetry receiver.
#
# Usage:
#   services.crabcc.receiver = {
#     enable   = true;
#     repoPath = "/opt/crabcc-autoresearch";
#     host     = "127.0.0.1";   # exposed via Caddy/nginx reverse proxy
#     port     = 8787;
#   };
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.crabcc.receiver;
  inherit (lib)
    mkEnableOption
    mkOption
    mkIf
    types
    ;
in
{
  options.services.crabcc.receiver = {
    enable = mkEnableOption "crabcc autoresearch FastAPI telemetry receiver";

    repoPath = mkOption {
      type = types.path;
      description = "Absolute path to the checked-out crabcc-autoresearch repository.";
      example = "/opt/crabcc-autoresearch";
    };

    host = mkOption {
      type = types.str;
      default = "127.0.0.1";
      description = ''
        Address to bind to. Use 127.0.0.1 when fronted by a reverse proxy
        (Caddy, nginx). Use a Tailscale address for mesh-only access.
      '';
      example = "100.64.0.1";
    };

    port = mkOption {
      type = types.port;
      default = 8787;
      description = "TCP port to listen on.";
    };

    stateDirectory = mkOption {
      type = types.str;
      default = "crabcc-receiver";
      description = "Name passed to StateDirectory= (resolves to /var/lib/<name>).";
    };

    openFirewall = mkOption {
      type = types.bool;
      default = false;
      description = "Open the receiver port in the firewall. Leave false when using a reverse proxy.";
    };
  };

  config = mkIf cfg.enable {
    systemd.services.crabcc-receiver = {
      description = "crabcc autoresearch telemetry receiver";
      after = [ "network.target" ];
      wantedBy = [ "multi-user.target" ];

      environment = {
        DB_PATH = "/var/lib/${cfg.stateDirectory}/runs.db";
      };

      serviceConfig = {
        Type = "simple";
        User = "crabcc-receiver";
        Group = "crabcc-receiver";
        WorkingDirectory = "${toString cfg.repoPath}/receiver";
        ExecStart = "${pkgs.uv}/bin/uv run uvicorn main:app --host ${cfg.host} --port ${toString cfg.port}";
        Restart = "on-failure";
        RestartSec = "5s";
        StateDirectory = cfg.stateDirectory;

        # Hardening
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
        ReadWritePaths = [
          "${toString cfg.repoPath}/receiver"
          "/var/lib/${cfg.stateDirectory}"
        ];
      };
    };

    users.users.crabcc-receiver = {
      isSystemUser = true;
      group = "crabcc-receiver";
      description = "crabcc autoresearch receiver service user";
    };

    users.groups.crabcc-receiver = { };

    networking.firewall.allowedTCPPorts = lib.mkIf cfg.openFirewall [ cfg.port ];
  };
}
