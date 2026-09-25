#!/usr/bin/env bash
# Fail if any plugin's version in the marketplace catalog differs from its
# own plugin.json. Runtimes disagree about which of the two they read (omp
# reads the catalog; claude/codex read plugin.json), so drift means different
# agents silently run different versions of the same plugin.
#
# Usage: scripts/check-versions.sh   (run from anywhere inside the repo)
set -euo pipefail

root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
catalog="$root/.claude-plugin/marketplace.json"

fail=0
while IFS=$'\t' read -r name source catalog_version; do
  manifest="$root/${source#./}/.claude-plugin/plugin.json"
  if [[ ! -f "$manifest" ]]; then
    echo "FAIL  $name: no plugin.json at ${manifest#"$root"/}"
    fail=1
    continue
  fi
  plugin_version="$(jq -r '.version // ""' "$manifest")"
  if [[ -z "$catalog_version" || -z "$plugin_version" ]]; then
    echo "FAIL  $name: missing version (catalog='${catalog_version}', plugin.json='${plugin_version}')"
    fail=1
  elif [[ "$catalog_version" != "$plugin_version" ]]; then
    echo "FAIL  $name: catalog says $catalog_version, plugin.json says $plugin_version"
    fail=1
  else
    echo "ok    $name $plugin_version"
  fi
done < <(jq -r '.plugins[] | [.name, .source, (.version // "")] | @tsv' "$catalog")

if [[ $fail -ne 0 ]]; then
  echo
  echo "Bump both .claude-plugin/marketplace.json and the plugin's .claude-plugin/plugin.json together."
fi
exit $fail
