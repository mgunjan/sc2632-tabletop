# Independent behavior checks

The fixed privilege checks cover six Pod CREATE behaviors only. They do not test networking, RBAC, debug subresources, existing workloads or exception cleanup. Run `kyverno test tests/` when kyverno-test.yaml is present. A passing check does not authorize deployment.
