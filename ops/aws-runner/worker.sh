#!/bin/bash
set -Eeuo pipefail
export AWS_DEFAULT_REGION='@@REGION@@'
export AWS_PAGER=''
export AWS_RETRY_MODE=standard
export AWS_MAX_ATTEMPTS=3
BUCKET='@@BUCKET@@'
PREFIX='@@PREFIX@@'
SOURCE='@@SOURCE@@'
SHA256='@@SHA256@@'

# Independent deadline applies even if installation or the benchmark stalls.
systemd-run --unit=ecosim-time-limit --on-active=20m /sbin/shutdown -h now
mkdir -p /opt/ecosim/results
exec > >(tee -a /var/log/ecosim-run.log /dev/console) 2>&1
finish() {
  rc=$?
  trap - EXIT
  set +e
  aws s3api put-object --bucket "$BUCKET" --key "$PREFIX/worker.log" --body /var/log/ecosim-run.log --server-side-encryption AES256
  printf '{"exit_code":%s,"source_sha256":"%s"}\n' "$rc" "$SHA256" > /opt/ecosim/status.json
  aws s3api put-object --bucket "$BUCKET" --key "$PREFIX/status.json" --body /opt/ecosim/status.json --server-side-encryption AES256
  shutdown -h now
  exit "$rc"
}
trap finish EXIT
cd /opt/ecosim
aws s3api get-object --bucket "$BUCKET" --key "$SOURCE" source.tar.gz
printf '%s  source.tar.gz\n' "$SHA256" | sha256sum --check -
tar -xzf source.tar.gz
dnf -y install python3.11 python3.11-pip
python3.11 -m venv venv
venv/bin/pip install --disable-pip-version-check --only-binary=:all: numpy==2.4.6
TOKEN=$(curl --fail --silent --show-error --max-time 5 -X PUT -H 'X-aws-ec2-metadata-token-ttl-seconds: 60' http://169.254.169.254/latest/api/token)
curl --fail --silent --show-error --max-time 5 -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/dynamic/instance-identity/document > results/instance.json
unset TOKEN
cp provenance.json results/provenance.json
venv/bin/python -m pip freeze > results/dependencies.txt
timeout --signal=TERM --kill-after=15s 600 venv/bin/python -m backend.tools.benchmarks.run_sim_bench --households 1000 --ticks 80 --seeds 42,43,44 --output-root results
venv/bin/python verify_results.py results > results/verification.json
tar -czf results.tar.gz results
sha256sum results.tar.gz > results.sha256
aws s3api put-object --bucket "$BUCKET" --key "$PREFIX/results.tar.gz" --body results.tar.gz --server-side-encryption AES256
aws s3api put-object --bucket "$BUCKET" --key "$PREFIX/results.sha256" --body results.sha256 --server-side-encryption AES256
echo 'EcoSim benchmark and S3 uploads completed.'
