"""One-shot EC2 lab using the AWS CLI, with a durable resource journal and cleanup.

Requires an explicitly authorized provisioning profile; never selects root or
escalates an operator profile automatically. No boto3 or persistent access keys.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time
import uuid

from verify_results import verify

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--region", choices=["us-west-2"], default="us-west-2")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    journal = args.output / "resources.json"
    state = {"region": args.region, "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]}

    def save():
        journal.write_text(json.dumps(state, indent=2) + "\n")

    def aws(service, operation, **params):
        region = "us-east-1" if service == "freetier" else args.region
        command = ["aws", service, operation, "--profile", args.profile, "--region", region,
                   "--output", "json", "--no-cli-pager"]
        for key, value in params.items():
            command.append("--" + key.replace("_", "-"))
            command.append(json.dumps(value) if isinstance(value, (dict, list)) else str(value))
        result = subprocess.run(command, capture_output=True, text=True, timeout=180,
                                env={**os.environ, "AWS_PAGER": "", "AWS_RETRY_MODE": "standard", "AWS_MAX_ATTEMPTS": "3"})
        if result.returncode:
            raise RuntimeError(f"{service} {operation}: {result.stderr.strip()}")
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def download(key, destination, missing_ok=False):
        result = subprocess.run(["aws", "s3api", "get-object", "--bucket", bucket, "--key", key,
            "--profile", args.profile, "--region", args.region, str(destination)],
            capture_output=True, text=True, timeout=60)
        if result.returncode:
            if missing_ok and "NoSuchKey" in result.stderr:
                return False
            raise RuntimeError(result.stderr)
        return True

    identity = aws("sts", "get-caller-identity")
    state["account"] = identity["Account"]
    state["provisioner"] = identity["Arn"]
    state["plan_before"] = aws("freetier", "get-account-plan-state")
    if state["plan_before"]["accountPlanType"] != "FREE" or state["plan_before"]["accountPlanStatus"] != "ACTIVE":
        raise RuntimeError("This lab is approved only for an active Free plan")
    commit = subprocess.check_output(["git", "-C", str(args.repo), "rev-parse", args.commit + "^{commit}"], text=True).strip()
    state["source_commit"] = commit
    vpcs = aws("ec2", "describe-vpcs", filters=[{"Name": "is-default", "Values": ["true"]}])["Vpcs"]
    if len(vpcs) != 1:
        raise RuntimeError("Expected one default VPC; do not create networking implicitly")
    vpc = vpcs[0]["VpcId"]
    subnets = aws("ec2", "describe-subnets", filters=[{"Name": "vpc-id", "Values": [vpc]}])["Subnets"]
    routes = aws("ec2", "describe-route-tables", filters=[{"Name": "vpc-id", "Values": [vpc]}])["RouteTables"]
    subnet = None
    for candidate in sorted(subnets, key=lambda s: s["AvailabilityZone"]):
        tables = [t for t in routes if any(a.get("SubnetId") == candidate["SubnetId"] for a in t["Associations"])]
        if not tables:
            tables = [t for t in routes if any(a.get("Main") for a in t["Associations"])]
        if candidate["AvailableIpAddressCount"] > 0 and any(
            r.get("DestinationCidrBlock") == "0.0.0.0/0" and r.get("GatewayId", "").startswith("igw-") and r.get("State") == "active"
            for t in tables for r in t["Routes"]
        ):
            subnet = candidate["SubnetId"]
            break
    if subnet is None:
        raise RuntimeError("No existing subnet with Internet Gateway egress; refusing NAT creation")
    ami = aws("ssm", "get-parameter", name="/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64")["Parameter"]["Value"]
    images = aws("ec2", "describe-images", image_ids=[ami], owners=["amazon"])["Images"]
    if len(images) != 1 or any(images[0][k] != v for k, v in {"Architecture": "x86_64", "State": "available", "RootDeviceType": "ebs", "VirtualizationType": "hvm"}.items()):
        raise RuntimeError("AMI validation failed")
    state.update(ami=ami, subnet=subnet, instance_type="t3.small")
    run_id = state["run_id"].lower()
    bucket = "ecosim-lab-" + run_id
    name = "ecosim-run-" + run_id
    prefix = "runs/" + run_id
    source_key = "source/" + run_id + ".tar.gz"
    provenance = {"source_commit": commit, "run_id": run_id, "source": "git archive: backend only; no working-tree files",
                  "workload": {"households": 1000, "ticks": 80, "seeds": [42, 43, 44]}, "numpy": "2.4.6"}
    bundle = args.output / "source.tar.gz"
    archive = subprocess.check_output(["git", "-C", str(args.repo), "archive", "--format=tar", commit, "backend"])
    with tarfile.open(fileobj=io.BytesIO(archive)) as original, tarfile.open(bundle, "w:gz") as target:
        for member in original:
            if member.issym() or member.islnk() or Path(member.name).is_absolute() or ".." in Path(member.name).parts:
                raise RuntimeError("Unexpected link or path in source archive")
            target.addfile(member, original.extractfile(member) if member.isfile() else None)
        for filename, contents in (("verify_results.py", (HERE / "verify_results.py").read_bytes()),
                                   ("provenance.json", json.dumps(provenance, indent=2).encode())):
            member = tarfile.TarInfo(filename)
            member.size = len(contents)
            target.addfile(member, io.BytesIO(contents))
    sha256 = hashlib.sha256(bundle.read_bytes()).hexdigest()
    state.update(bucket=bucket, prefix=prefix, source_key=source_key, source_sha256=sha256)
    save()
    tags = [{"Key": "Project", "Value": "EcoSim"}, {"Key": "Purpose", "Value": "ResumeLab"}, {"Key": "RunId", "Value": run_id}]
    arn = f"arn:aws:s3:::{bucket}"
    worker_policy = {"Version": "2012-10-17", "Statement": [
        {"Effect": "Allow", "Action": "s3:GetObject", "Resource": arn + "/" + source_key},
        {"Effect": "Allow", "Action": "s3:PutObject", "Resource": arn + "/" + prefix + "/*"},
    ]}
    (args.output / "worker-policy.json").write_text(json.dumps(worker_policy, indent=2))
    cleanup_errors = []
    try:
        aws("s3api", "create-bucket", bucket=bucket, create_bucket_configuration={"LocationConstraint": args.region},
            object_ownership="BucketOwnerEnforced")
        state["bucket_created"] = True
        save()
        aws("s3api", "put-public-access-block", bucket=bucket, public_access_block_configuration={k: True for k in
            ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")})
        aws("s3api", "put-bucket-encryption", bucket=bucket, server_side_encryption_configuration={"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]})
        aws("s3api", "put-bucket-versioning", bucket=bucket, versioning_configuration={"Status": "Enabled"})
        aws("s3api", "put-bucket-tagging", bucket=bucket, tagging={"TagSet": tags})
        aws("s3api", "put-bucket-policy", bucket=bucket, policy={"Version": "2012-10-17", "Statement": [
            {"Sid": "DenyInsecureTransport", "Effect": "Deny", "Principal": "*", "Action": "s3:*", "Resource": [arn, arn + "/*"], "Condition": {"Bool": {"aws:SecureTransport": "false"}}}]})
        aws("s3api", "put-bucket-lifecycle-configuration", bucket=bucket, lifecycle_configuration={"Rules": [
            {"ID": "AbortIncompleteUploads", "Status": "Enabled", "Filter": {"Prefix": ""}, "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 1}}]})
        aws("s3api", "put-object", bucket=bucket, key=source_key, body=str(bundle), server_side_encryption="AES256")
        aws("iam", "create-role", role_name=name, tags=tags, assume_role_policy_document={"Version": "2012-10-17", "Statement": [
            {"Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"}, "Action": "sts:AssumeRole"}]})
        state["role"] = name
        save()
        aws("iam", "put-role-policy", role_name=name, policy_name="EcoSimRunObjects", policy_document=worker_policy)
        aws("iam", "create-instance-profile", instance_profile_name=name, tags=tags)
        state["instance_profile"] = name
        save()
        aws("iam", "add-role-to-instance-profile", instance_profile_name=name, role_name=name)
        sg = aws("ec2", "create-security-group", group_name=name, description="EcoSim batch runner; no inbound access", vpc_id=vpc,
                 tag_specifications=[{"ResourceType": "security-group", "Tags": tags}])["GroupId"]
        state["security_group"] = sg
        save()
        aws("ec2", "revoke-security-group-egress", group_id=sg, ip_permissions=[{"IpProtocol": "-1", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}])
        aws("ec2", "authorize-security-group-egress", group_id=sg, ip_permissions=[{"IpProtocol": "tcp", "FromPort": 443, "ToPort": 443, "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "HTTPS package downloads and S3"}]}])
        script = (HERE / "worker.sh").read_text()
        for key, value in {"REGION": args.region, "BUCKET": bucket, "PREFIX": prefix, "SOURCE": source_key, "SHA256": sha256}.items():
            script = script.replace("@@" + key + "@@", value)
        user_data = args.output / "user-data.sh"
        user_data.write_text(script)
        # IAM instance-profile propagation is eventually consistent.
        time.sleep(15)
        state["launch_requested"] = True
        save()
        instance = aws("ec2", "run-instances", image_id=ami, instance_type="t3.small", count=1,
            client_token=run_id, iam_instance_profile={"Name": name}, user_data="file://" + str(user_data.resolve()),
            network_interfaces=[{"DeviceIndex": 0, "SubnetId": subnet, "Groups": [sg], "AssociatePublicIpAddress": True, "DeleteOnTermination": True}],
            metadata_options={"HttpTokens": "required", "HttpEndpoint": "enabled", "HttpPutResponseHopLimit": 1},
            credit_specification={"CpuCredits": "standard"}, instance_initiated_shutdown_behavior="terminate",
            block_device_mappings=[{"DeviceName": images[0]["RootDeviceName"], "Ebs": {"VolumeSize": 8, "VolumeType": "gp3", "Encrypted": True, "DeleteOnTermination": True}}],
            tag_specifications=[{"ResourceType": r, "Tags": tags + [{"Key": "Name", "Value": name}]} for r in ("instance", "volume")])["Instances"][0]
        state["instance_id"] = instance["InstanceId"]
        state["launched_at"] = datetime.now(timezone.utc).isoformat()
        save()
        print(f"Launched {state['instance_id']}; results s3://{bucket}/{prefix}/", flush=True)
        deadline = time.monotonic() + 20 * 60
        status_file = args.output / "status.json"
        while time.monotonic() < deadline:
            if download(prefix + "/status.json", status_file, missing_ok=True):
                break
            time.sleep(20)
        else:
            raise TimeoutError("20-minute run deadline exceeded")
        status = json.loads(status_file.read_text())
        state["worker_status"] = status
        save()
        download(prefix + "/worker.log", args.output / "worker.log")
        if status["exit_code"] != 0 or status["source_sha256"] != sha256:
            raise RuntimeError(f"Cloud worker failed: {status}")
        for filename in ("results.tar.gz", "results.sha256"):
            download(prefix + "/" + filename, args.output / filename)
        expected = (args.output / "results.sha256").read_text().split()[0]
        if hashlib.sha256((args.output / "results.tar.gz").read_bytes()).hexdigest() != expected:
            raise RuntimeError("S3 round-trip checksum mismatch")
        with tarfile.open(args.output / "results.tar.gz") as results:
            results.extractall(args.output, filter="data")
        instance_evidence = json.loads((args.output / "results/instance.json").read_text())
        if instance_evidence["instanceId"] != state["instance_id"] or instance_evidence["region"] != args.region:
            raise RuntimeError("Cloud instance evidence mismatch")
        verified = verify(args.output / "results")
        state["verification"] = verified
        operator_policy = {"Version": "2012-10-17", "Statement": [
            {"Effect": "Allow", "Action": "s3:GetObject", "Resource": arn + "/runs/*"},
            {"Effect": "Allow", "Action": "s3:ListBucket", "Resource": arn, "Condition": {"StringLike": {"s3:prefix": ["runs/", "runs/*"]}}},
        ]}
        aws("iam", "put-user-policy", user_name="ecosim-operator", policy_name="EcoSimResults-" + run_id, policy_document=operator_policy)
        state["operator_policy_name"] = "EcoSimResults-" + run_id
        (args.output / "operator-policy.json").write_text(json.dumps(operator_policy, indent=2))
        save()
        print("Verified three complete cloud runs and S3 SHA-256 round trip.", flush=True)
    finally:
        def clean(service, operation, **params):
            for attempt in range(6):
                try:
                    aws(service, operation, **params)
                    return True
                except Exception as exc:
                    if attempt == 5:
                        cleanup_errors.append(str(exc))
                    else:
                        time.sleep(10)
            return False

        if state.get("launch_requested") and not state.get("instance_id"):
            try:
                reservations = aws("ec2", "describe-instances", filters=[{"Name": "client-token", "Values": [run_id]}])["Reservations"]
                recovered = [i["InstanceId"] for r in reservations for i in r["Instances"]]
                if len(recovered) == 1:
                    state["instance_id"] = recovered[0]
                    save()
                elif recovered:
                    cleanup_errors.append("Multiple instances matched client token: " + str(recovered))
            except Exception as exc:
                cleanup_errors.append(str(exc))
        if state.get("instance_id"):
            clean("ec2", "terminate-instances", instance_ids=[state["instance_id"]])
            try:
                result = subprocess.run(["aws", "ec2", "wait", "instance-terminated", "--instance-ids", state["instance_id"],
                                         "--profile", args.profile, "--region", args.region], capture_output=True, text=True, timeout=300)
                if result.returncode:
                    cleanup_errors.append(result.stderr)
                else:
                    state["instance_terminated"] = True
            except Exception as exc:
                cleanup_errors.append(str(exc))
        if state.get("security_group"):
            clean("ec2", "delete-security-group", group_id=state["security_group"])
        if state.get("instance_profile"):
            clean("iam", "remove-role-from-instance-profile", instance_profile_name=name, role_name=name)
            clean("iam", "delete-instance-profile", instance_profile_name=name)
        if state.get("role"):
            clean("iam", "delete-role-policy", role_name=name, policy_name="EcoSimRunObjects")
            clean("iam", "delete-role", role_name=name)
        state["cleanup_errors"] = cleanup_errors
        state["finished_at"] = datetime.now(timezone.utc).isoformat()
        save()
        print(f"Cleanup complete; {len(cleanup_errors)} errors. Journal: {journal}", flush=True)
    if cleanup_errors:
        raise RuntimeError("Cleanup needs attention; inspect resources.json")


if __name__ == "__main__":
    main()
