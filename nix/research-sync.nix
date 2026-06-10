# NixOS module — systemd rsync timer that mirrors autoresearch slot artifacts
# from the ephemeral GPU worker to the Hetzner receiver host via Tailscale.
#
# Usage:
#   services.crabcc.researchSync = {
#     enable      = true;
#     workerHost  = "gpu-worker-01";   # Tailscale hostname
#     slots       = [ "lambda" "charlm" ];
#   };
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.crabcc.researchSync;
  inherit (lib)
    mkEnableOption
    mkOption
    mkIf
    types
    concatMapStringsSep
    ;
in
{
  options.services.crabcc.researchSync = {
    enable = mkEnableOption "crabcc autoresearch artifact sync timer";

    workerHost = mkOption {
      type = types.str;
      default = "gpu-research-worker-01";
      description = "Tailscale hostname of the GPU worker to sync from.";
      example = "vast-4090-worker";
    };

    workerUser = mkOption {
      type = types.str;
      default = "root";
      description = "SSH user on the worker. The sync service user must be able to authenticate as this user.";
    };

    workerBasePath = mkOption {
      type = types.str;
      default = "/root/crabcc-autoresearch/worker";
      description = "Absolute path to the worker directory on the GPU instance.";
    };

    stateDirectory = mkOption {
      type = types.str;
      default = "crabcc-research";
      description = "Name passed to StateDirectory= (resolves to /var/lib/<name>).";
    };

    slots = mkOption {
      type = types.listOf types.str;
      default = [
        "lambda"
        "charlm"
      ];
      description = "Autoresearch slot names to sync. Each maps to slots/<name>/ on the worker.";
      example = [ "lambda" ];
    };

    interval = mkOption {
      type = types.str;
      default = "10m";
      description = "How often to poll the worker (OnUnitActiveSec).";
      example = "5m";
    };

    user = mkOption {
      type = types.str;
      default = "root";
      description = ''
        System user to run the sync service as. This user must be able to SSH
        to workerHost as workerUser. Consider creating a dedicated system user
        with a restricted SSH key rather than using root.
      '';
    };
  };

  config = mkIf cfg.enable {
    systemd.services.crabcc-research-sync = {
      description = "Sync crabcc autoresearch artifacts from GPU worker";
      after = [
        "network-online.target"
        "tailscaled.service"
      ];
      wants = [ "network-online.target" ];
      requires = [ "tailscaled.service" ];

      serviceConfig = {
        Type = "oneshot";
        User = cfg.user;
        StateDirectory = cfg.stateDirectory;
        ExecStart = pkgs.writeShellScript "crabcc-research-sync" ''
          set -euo pipefail
          WORKER="${cfg.workerHost}"
          DEST="/var/lib/${cfg.stateDirectory}"

          if ! ${pkgs.iputils}/bin/ping -c 1 -W 5 "$WORKER" > /dev/null 2>&1; then
            echo "Worker $WORKER not reachable on Tailscale, skipping" >&2
            exit 0
          fi

          ${concatMapStringsSep "\n" (slot: ''
            mkdir -p "$DEST/slots/${slot}"
            ${pkgs.rsync}/bin/rsync -az --ignore-missing-args \
              "${cfg.workerUser}@$WORKER:${cfg.workerBasePath}/slots/${slot}/results.tsv" \
              "${cfg.workerUser}@$WORKER:${cfg.workerBasePath}/slots/${slot}/train.py" \
              "$DEST/slots/${slot}/"
          '') cfg.slots}

          echo "Synced ${toString (builtins.length cfg.slots)} slot(s) from $WORKER"
        '';
      };
    };

    systemd.timers.crabcc-research-sync = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "2m";
        OnUnitActiveSec = cfg.interval;
        Unit = "crabcc-research-sync.service";
        Persistent = true;
      };
    };
  };
}
