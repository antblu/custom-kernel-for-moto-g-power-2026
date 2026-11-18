# Contributing

Run the offline tests before proposing changes. Describe the firmware, kernel release, method, and result for each compatibility claim. Separate build results from device test results. Preserve dependencies and test kernel configuration changes one group at a time.

Install the repository hooks with `pre-commit install`. The hooks check the Git index and scan staged changes for secrets. CI checks the index and scans the fetched Git history.

Use the allowlisted ADB report as a starting point for compatibility reports. Keep device identifiers, raw diagnostics, firmware, modules, partition backups, local paths, network details, and credentials outside tracked files. Check the staged file list, full staged diff, secret and privacy scan results, binary file types, redistribution rights, and commit identity before publication. Resolve any scanner failures or suspected disclosures before pushing.

Use an approved public commit identity. Initial publication and releases require maintainer approval. Report suspected leaks or security vulnerabilities privately to the maintainer through an approved channel.
