# Immutable production release contract

`deploy.sh` is an attended future action, not a source-staging command. It
requires one finalized `sapphire/deploy-action/v1` descriptor and the SHA-256
of that exact descriptor.

The descriptor binds:

- the exact clean Git commit, deterministic archive, manifest, existing GCS
  bucket, object, and positive object generation;
- a SHA-256 commitment to the exact bucket configuration;
- the complete pre-action Cloud Run generation, observed generation, ready and
  created revisions plus image digests, traffic, IAM policy, service account,
  full runtime environment, service URL, and expected `/api/build` status;
- the exact post-action IAM, service account, full environment commitment and
  service URL; the verifier additionally requires generation-plus-one, a new
  singular ready/created revision, 100% traffic, the built image digest, and a
  healthy `/api/build`;
- SHA-256 identities for `deploy.sh`, `cloudbuild.yaml`, the preflight/CAS,
  postcheck, dependency locks, Dockerfile, and network-asset lock.

Source staging is deliberately separate. The source object must already exist
with custom metadata `sha256=<archive SHA-256>`. Neither `deploy.sh` nor the
Cloud Build command creates a bucket or uploads source. `deploy.sh` renders a
temporary Cloud Build request with that exact storage generation and uses
`--no-source`, so the SDK's implicit `CreateBucketIfNotExists` path is not
entered.

The final Cloud Build step reruns artifact/provenance checks and then performs
the remote-state compare-and-swap immediately before `exec gcloud run deploy`.
Any drift makes the step fail before the deploy process starts. The descriptor
and rendered build request are candidate-specific artifacts and must be
generated and independently reviewed after the merge commit and source object
generation exist.
