# Ubuntu Live Image

This configuration builds a non-installing Ubuntu 24.04 LTS amd64 hybrid ISO. It boots to the Battery OS CLI on tty1 using the unprivileged `batteryos` account and enables Casper persistence. The image does not partition, format, or install to the computer's internal drive.

## Build

Build from an Ubuntu 24.04 amd64 host with root privileges and internet access. Install the image tools first:

```sh
sudo apt-get update
sudo apt-get install live-build debootstrap squashfs-tools xorriso grub-pc-bin grub-efi-amd64-bin mtools dosfstools
sudo python3 scripts/build_ubuntu_live_image.py
```

The build driver stages the application under `build/ubuntu-live/config/includes.chroot/opt/battery-os`, configures Ubuntu Noble, and runs `lb build`. The resulting ISO is written inside `build/ubuntu-live/`.

Allow substantial free disk space for the chroot and ISO. The build requires root inside Linux; it does not automatically install build dependencies or write to USB devices.

## Boot

Write the generated hybrid ISO to a USB drive using a trusted imaging tool, then select that USB drive in the firmware boot menu. Writing the image erases the selected USB drive; double-check the target device. This is separate from building the ISO.

## Persistent USB Setup

Persistence uses Ubuntu Casper's `persistent` boot option and looks for a writable ext4 partition labeled `casper-rw`. Keep this partition separate from the ISO's boot/system partitions.

1. Flash the generated ISO to the USB using a trusted image writer. This erases the USB; verify the target device carefully and back up anything on it first.
2. Use a partition tool such as GParted to create an ext4 partition in the USB's unused space. Label it exactly `casper-rw`. Do not resize or format the ISO's existing partitions as part of this step.
3. Boot the USB from the firmware boot menu. Casper should mount the `casper-rw` partition as the writable overlay; files, settings, and notes should then survive reboot.

The build script only creates the ISO; it never writes to a USB device or creates partitions. If the image writer leaves no unallocated space, stop rather than modifying the boot partitions. Use a larger USB or a persistence-capable image writer.

The persistence partition is not encrypted. Anyone with access to the USB may be able to read its contents. Keep a separate backup of important files. The image remains a live environment, not an installer, and hardware boot/persistence still need validation on the target laptop.