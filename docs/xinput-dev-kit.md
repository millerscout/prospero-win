# Xinput kit graft

This branch's controller changes are not a new kit. Build Wine's PS5 runtime
on an x86-64 Linux host, then graft `ntdll.prx`, `xinput1_3.prx`, and the
xinput PE modules onto an unpacked official Playden kit 0.17.
`tools/update_kit_xinput_from_cross.py` keeps `kit_id` `playden-kit`.

The scripts configure as `x86_64-pc-linux-gnu`. They need
`i686-w64-mingw32-gcc` and `x86_64-w64-mingw32-gcc` (Manjaro:
`mingw-w64-gcc`). An aarch64 host cannot build this. Mesa, GnuTLS, and
`tools/package_playden_kit.py` stay out of this try.

`PS5_PRX_FOUNDATION` must contain module-export commit
`30597512539e7edfde079cbcaf4a626bc0a948c5` or
`e879c08a408ac17186b4736d86f67bcc1aa9dab8`. Without that checkout the PRX
link is skipped.

```sh
uname -m    # x86_64
export PS5_PAYLOAD_SDK=/path/to/ps5-payload-sdk
export PS5_NATIVE_FOUNDATION=/path/to/ps5-native-app-boilerplate
export PS5_PRX_FOUNDATION=/path/to/foundation-with-module-exports
tools/build_host_wine.sh
PROSPERO_WINE_SOURCE="$PWD/.deps/wine/source" \
PROSPERO_WINE_BUILD="$PWD/.deps/wine-host/build" \
  tools/build_wine_ps5.sh
```

`build_host_wine.sh` prints the installed Wine path last. Point
`PROSPERO_WINE_BUILD` at that build directory if it is not
`.deps/wine-host/build`. The graft reads `.deps/wine-ps5/prx/sce_module`
and `.deps/wine-ps5/pe`. An older `.deps/wine-ps5` is the previous runtime:
the script checks out Wine `490f6d5dcbb2a5047345b8af88d114bbcaad69a8` and
reapplies `wine/patches` from this tree.

The any-title shell is built on the Mac with `PW_ANY_TITLE=1 tools/build_native.sh`.
Download and unzip official `playden-kit-0.17`, then:

```sh
python3 tools/update_kit_xinput_from_cross.py \
  --from-kit /path/to/playden-kit-0.17 \
  --cross /path/to/.deps/wine-ps5 \
  --out /path/to/playden-kit-xinput-dev \
  --title-eboot /path/to/eboot.bin
```

`--cross` defaults to `.deps/wine-ps5`. `--title-eboot` is optional. The
default artifact revision is `6d2a7c6-kit-xinput-dev1`.

From the playden-ps5 tree:

```sh
python3 tools/console_kit_upload.py /path/to/playden-kit-xinput-dev --host <PS5 IP> --replace
```

That replaces `/data/playden/kits/playden-kit` after hashing every file.
Playden loads that directory. The new manifest hash will not equal the pin
in playden-ps5 `src/runtime/kit_trust.h`, so Playden offers official kit
0.17 again. Leaving that offer alone keeps the grafted kit. Games take the
new shell and runtime when Play is pressed.
