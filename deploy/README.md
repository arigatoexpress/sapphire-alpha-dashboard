# Immutable production release contract

`deploy.sh` is the one-button attended future action. The external approval
harness is the trust root: before invoking it, the harness must SHA-256 pin the
wrapper, resolved Python interpreter, and `scripts/trusted_release.py` in
`SAPPHIRE_TRUSTED_WRAPPER_SHA256`,
`SAPPHIRE_TRUSTED_PYTHON_SHA256` and
`SAPPHIRE_TRUSTED_LAUNCHER_SHA256`, and must independently pin
`scripts/deploy_contract.py` in `SAPPHIRE_TRUSTED_GUARD_SHA256`. The launcher
also requires externally captured `SAPPHIRE_TRUSTED_GIT_SHA256`,
`SAPPHIRE_TRUSTED_GCLOUD_SHA256`, and
`SAPPHIRE_TRUSTED_RENDERED_CONFIG_SHA256`. It verifies its own bytes, canonical
descriptor shape, complete fixed artifact closure, local tool executables, and
the exact rendered build request before compiling or submitting the action.

The descriptor binds:

- the exact clean Git commit and tree, deterministic archive SHA-256 and MD5,
  canonical tracked-file manifest and count, existing GCS object, and positive
  generation;
- SHA-256 commitments to the bucket's full raw resource document and IAM
  policy, including its owning project number;
- the complete pre-action Cloud Run generation, observed generation, ready and
  created revisions plus image digests, traffic, IAM policy, service account,
  full runtime environment, service URL, and expected `/api/build` status;
- the exact post-action IAM, service account, full environment commitment,
  service URL, source SHA, and byte manifests for both frontends. The verifier
  additionally requires generation-plus-one, a new singular ready/created
  revision, 100% traffic, the immutable built image digest, exact build ID and
  runtime revision, and a healthy `/api/build`;
- SHA-256 identities for `deploy.sh`, `cloudbuild.yaml`, the preflight/CAS,
  postcheck, dependency locks, Dockerfile, and network-asset lock.

Source staging is deliberately separate. `trusted_release.py seal-source`
creates a deterministic local archive containing a canonical
`.sapphire-source-manifest.json`; upload is a separately reviewed operation.
The attended action downloads the exact generation and hashes its bytes rather
than trusting custom metadata. It also regenerates the archive from the exact
clean Git tree locally. Neither the launcher nor Cloud Build creates a bucket
or uploads source.

After the exact archive generation exists, `trusted_release.py draft-action
--object <source/sapphire/...tar.gz> --generation <positive-int> --output
<action.json>` performs read-only bucket/object/service inspection and writes a
mode-0600 canonical descriptor. It refuses a dirty Git tree, re-downloads the
specified generation, runs both pinned Linux/amd64 scratch proof stages,
requires the reviewed Git tree to remain clean, and checks the 4,000-byte
substitution ceiling. The resulting container-platform entrypoint, asset-count,
and manifest commitments become deployment postconditions.

Cloud Build only verifies the extracted workspace, builds, and pushes. The
trusted launcher waits for terminal `SUCCESS`, verifies real generation-qualified
Cloud Build provenance and its single image digest, and deploys
`repository@sha256:digest`. The Cloud Run v1 replacement carries the previously
reviewed `metadata.resourceVersion`, so the provider rejects a stale action
atomically. Readback is retried only after that compare-and-swap succeeds.

The atomic boundary covers the Cloud Run Service resource (template,
environment, service account, and traffic). Service IAM is a separate Google
resource and cannot participate in the same transaction: it is hashed in the
immediate preflight and required byte-for-byte in the postcheck, but a
concurrent IAM writer inside that narrow interval is a residual attended risk.
This action never writes IAM.
