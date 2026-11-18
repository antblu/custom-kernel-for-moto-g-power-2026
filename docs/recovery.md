# Boot and recovery findings

For vegas26 firmware W1WEOS36.48-22-3-3-4-2, the active boot partition was backed up privately and its SHA-256 matched the on-device partition. The stock boot header is v4. The separate `init_boot` and `vendor_boot` partitions carry the generic and vendor ramdisks.

The active `vbmeta` uses SHA256_RSA2048 with flags zero and contains a hash descriptor for `boot`. Replacing the kernel payload changes the digest covered by that descriptor.

The bootloader accepted temporary downloads of the full stock boot backup and of the original stock image up to the AVB footer's recorded image length. Both download attempts returned to Fastboot. This firmware has no verified temporary boot path in the project. Fastboot recognized slot A and the boot partition size, but the slot-success and slot-unbootable queries returned no usable results. A stock-only restore rehearsal wrote the checksum-verified backup to boot_a in bootloader Fastboot. Stock Android booted on slot A afterward, root worked, and the partition SHA-256 matched the backup.

Motorola documents Software Fix as a factory-reset recovery procedure that installs current matching firmware and removes personal data. Its documentation alone leaves model-specific recovery on this test device unverified. [Motorola Software Fix recovery](https://en-us.support.motorola.com/app/answers/detail/a_id/167770/~/how-to-run-a-rescue-software-update/)

The namespace candidate was packaged privately as an unsigned v4 boot image with a gzip kernel. It occupies 22,003,712 bytes, fits the 64 MiB partition, and its decompressed kernel matches the audited build manifest. This checks the image layout and kernel contents. Fastboot accepted the unsigned candidate when flashed to boot_a, and Android booted with the stock init_boot, vendor_boot, and vbmeta in place. USB took longer to reappear than the first status probe allowed. The verified stock backup remains the rollback image.
