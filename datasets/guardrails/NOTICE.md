# Upstream attribution

This collection derives policy, test and rule content from these Apache-2.0 repositories, at the immutable revisions in `sources.lock.json`:

- Kyverno policies: https://github.com/kyverno/policies — copyright the Kyverno project contributors.
- Falco rules: https://github.com/falcosecurity/rules — copyright The Falco Authors.
- Falco testing: https://github.com/falcosecurity/testing — copyright The Falco Authors.
- Falco event-generator: https://github.com/falcosecurity/event-generator — copyright The Falco Authors.

Their license texts are retained in `licenses/`. Source references identify the exact original file and revision for each catalog entry and expectation. The normalized JSON records are a transformation of those files, not an upstream release or endorsement.

The replay configuration derives from the Apache-2.0 Falco 0.45.0 image's default configuration. The container metadata plugin is loaded with all runtime engines disabled, configuration includes disabled, and the capture source set to replay.

The historical syscall archives from `download.falco.org` are fetched from the original URLs and retained only in the ignored local cache. A separate redistribution license for those archives has not been established here; raw captures and their event logs are not included in the public source package. The lock retains their URL, size and SHA-256. The Kyverno executable and container images are external execution dependencies and are not redistributed in this package.
