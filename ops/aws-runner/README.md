# EcoSim AWS Batch Lab

A small, disposable EC2 runner for the existing Python simulation benchmark.
This is **not** a deployment of the interactive frontend, a production service,
an LLM service, or a distributed simulation. No model-provider credentials are
used. Infrastructure is managed with a Python script calling the AWS CLI, not
CloudFormation, Terraform, Kubernetes, or a CI/CD pipeline.

## Architecture

1. An explicitly authorized provisioning profile creates an encrypted, private,
   versioned S3 bucket and uploads a bundle from an explicit Git commit.
2. One Amazon Linux 2023 `t3.small` runs the existing benchmark: 1,000 households,
   80 ticks, seeds 42/43/44. Only NumPy is needed by this benchmark path.
3. An EC2 instance role can read exactly that source object and write only that
   run's result prefix. It has no IAM, account, bucket-administration, or compute
   permissions. No access keys are copied to the instance.
4. Results, provenance, instance identity, and logs are uploaded to S3. The local
   script downloads them, verifies their SHA-256 checksum, checks every run for
   failure/completion, and grants the existing `ecosim-operator` read access to
   that bucket's `runs/` prefix only.
5. OS shutdown terminates the instance and deletes its encrypted root volume.
   A 20-minute OS timer and the local script's 20-minute deadline bound normal
   execution. The local `finally` block also terminates compute and removes the
   temporary instance profile, IAM role, and security group.

The existing default VPC is reused. There are no inbound rules and no SSH key.
A temporary public IPv4 address allows outbound HTTPS downloads without a NAT
Gateway. The security group permits only TCP 443 egress; IMDSv2 is required.
T3 CPU credits are set to `standard`, so the workload can be throttled instead
of accumulating surplus CPU-credit charges. This favors a bounded lab over
maximum benchmark performance.

## Verified run

On 2026-10-03 this script completed one run in `us-west-2`. All three seeded
benchmark runs (1,000 households, 80 ticks, seeds 42/43/44) finished, and the
results archive matched its SHA-256 checksum after the S3 round trip. The
instance, its root volume, the workload role and instance profile, and the
security group were removed afterward. Only the private results bucket and the
operator's read access to its `runs/` prefix remain. The results are not
committed to this repository.

## Run

Prerequisites: Python 3.11.9+ (tar extraction filters), Git, AWS CLI v2, an active
Free-plan account, an existing default VPC with Internet Gateway routing, and
an existing `ecosim-operator` IAM user. Resources are limited to `us-west-2`.

Authentication is separate from authorization. `ecosim` is an everyday,
non-root profile and is intentionally unable to provision this infrastructure.
Do not broaden it or silently fall back to another profile after AccessDenied.
Use a separately authorized provisioning profile. For this initial lab, the
owner explicitly authorized a temporary `ecosim-bootstrap` browser login.
Never configure that profile in any agent's MCP profile list.

Browser sign-in and password/MFA enrollment are completed by the account owner.

From the repository root, after explicit authorization and browser login:

```bash
python3 ops/aws-runner/run_cloud.py \
  --repo "$PWD" \
  --commit <reviewed-full-commit-sha> \
  --profile ecosim-bootstrap \
  --output /absolute/path/outside-the-repo/new-run-directory \
  --execute
```

The output directory must not exist. The script archives committed `backend/`
files only; it never includes uncommitted changes, `.env` files from the working
tree, local AWS configuration, or login caches. Inspect committed source before
uploading it. NumPy is pinned to the version in the benchmark's source lockfile
at the verified revision; review the pin when changing revisions.

The resource journal is `resources.json`. It contains deployment identifiers,
not credentials, and belongs outside Git. The script does not upgrade plans,
create Organizations, create access keys, open ports, or modify existing VPCs.

## Verify And Recover

```bash
python3 -m unittest discover -s ops/aws-runner -p 'test_*.py' -v
bash -n ops/aws-runner/worker.sh
python3 ops/aws-runner/verify_results.py /path/to/downloaded/results
```

A benchmark exit code of zero is insufficient: individual failed runs are
recorded in `raw.json`. The verifier rejects missing artifacts, wrong seeds,
failed or incomplete runs, and an incorrect tick count.

Success requires `verification.verified: true`, `instance_terminated: true`,
and an empty `cleanup_errors` list in the resource journal. Also check that
there are no remaining volumes tagged with that run's `RunId`. If interrupted,
use the exact journal identifiers to terminate the instance, wait for termination,
then delete its security group, detach/delete the instance profile, and delete
its inline role policy and role. Do not delete unrelated resources.

S3 results and the source bundle are intentionally retained. Versioning is not
an immutable backup: authorized deletion of all versions can still remove data.
The lifecycle rule aborts incomplete multipart uploads only; it does not expire
the retained evidence. For final account cleanup, download and verify the
results first, obtain approval to delete retained data, then remove all object
versions/delete markers and the dedicated bucket and operator inline policy.
Do not delete an arbitrary bucket or suspend versioning to hide retained costs.

After provisioning and verification:

```bash
aws logout --profile ecosim-bootstrap
aws sts get-caller-identity --profile ecosim
```

Remove the now-unused bootstrap profile configuration as well. Logout does not
necessarily revoke a token already loaded by another process immediately.
Leave the ordinary operator profile and its least-privilege permissions intact.

## Cost And Interview Scope

This is a short-lived learning lab, not an always-on service. Check current
[EC2](https://aws.amazon.com/ec2/pricing/on-demand/),
[EBS](https://aws.amazon.com/ebs/pricing/),
[public IPv4](https://aws.amazon.com/vpc/pricing/), and
[S3](https://aws.amazon.com/s3/pricing/) rates before rerunning. The owner's
initial approval capped the verification run at $1 of credits; it does not
authorize unlimited future runs. An OS timer is a backstop, not an AWS billing
hard cap. Billing/credit reporting may lag. S3 storage remains after compute is
removed and continues consuming a small amount of credits.

Explain the design as EC2 for an existing CPU-bound Python job, S3 for durable
results after termination, and IAM roles for temporary, scoped workload access.
Resume claims should mention only verified work. Do not claim production scale,
high availability, autoscaling, a deployed web application, CloudWatch logging,
or measured performance improvements based on this lab.
