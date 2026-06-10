# nix/crabcc-research-sync.nix
# Drop-in module for nix-base. Import in the relevant host config:
#   imports = [ ./crabcc-research-sync.nix ];
{ pkgs, ... }:

{
  systemd.services.crabcc-research-sync = {
    description = "Sync autoresearch results.tsv from ephemeral GPU worker";
    after = [ "network-online.target" "tailscaled.service" ];
    requires = [ "tailscaled.service" ];
    serviceConfig = {
      Type = "oneshot";
      User = "root";
      ExecStart = pkgs.writeShellScript "sync-research" ''
        set -e
        WORKER="gpu-research-worker-01"
        DEST="/var/lib/crabcc-research"
        mkdir -p "$DEST"
        if ${pkgs.iputils}/bin/ping -c 1 -W 5 "$WORKER" > /dev/null 2>&1; then
          ${pkgs.rsync}/bin/rsync -avz \
            "root@$WORKER:/root/crabcc-autoresearch/worker/results.tsv" \
            "$DEST/"
          echo "Synced results.tsv from $WORKER"
        else
          echo "Worker $WORKER not reachable on Tailscale, skipping sync" >&2
        fi
      '';
    };
  };

  systemd.timers.crabcc-research-sync = {
    wantedBy = [ "timers.target" ];
    timerConfig = {
      OnBootSec = "2m";
      OnUnitActiveSec = "10m";
      Unit = "crabcc-research-sync.service";
      Persistent = true;
    };
  };
}
