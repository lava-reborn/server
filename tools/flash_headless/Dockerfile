# The real Flash Player 32 projector under Wine on a virtual X screen, for
# tools/flash_headless/run.sh (README.md beside this file). Built once, with
# the network, from this folder: run.sh tags it by the hash of this file,
# host.as and skel.py and builds it when that tag is missing. It runs with
# --network none; the projector itself is never baked in, run.sh mounts the
# one it is given.

# Stage "film": FFDec, pinned by version and sha256, compiles host.as into
# the empty film skel.py writes. Only the compiled film leaves this stage.
FROM debian:trixie-slim AS film
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      default-jre-headless curl ca-certificates unzip python3 && \
    rm -rf /var/lib/apt/lists/*
ARG FFDEC_VERSION=26.3.0
ARG FFDEC_SHA256=35f4930eb7c380afe66f2117f90b006deac0631473ad7500bb39c78f68645ecd
RUN curl -fsSL -o /tmp/ffdec.zip \
      "https://github.com/jindrapetrik/jpexs-decompiler/releases/download/version${FFDEC_VERSION}/ffdec_${FFDEC_VERSION}.zip" && \
    echo "${FFDEC_SHA256}  /tmp/ffdec.zip" | sha256sum -c - && \
    mkdir /opt/ffdec && unzip -q /tmp/ffdec.zip -d /opt/ffdec && rm /tmp/ffdec.zip
COPY skel.py host.as /film/
RUN cd /film && python3 skel.py skel.swf && \
    java -Djava.awt.headless=true -jar /opt/ffdec/ffdec-cli.jar -export script src skel.swf && \
    cp host.as src/scripts/frame_1/DoAction.as && \
    java -Djava.awt.headless=true -jar /opt/ffdec/ffdec-cli.jar -importScript skel.swf host_script.swf src/scripts && \
    test -s host_script.swf

# The player's image: Wine (32-bit, the projector is a 32-bit exe), Xvfb,
# ImageMagick for a picture of the virtual screen, Python for the stand and
# the checks.
FROM debian:trixie-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN dpkg --add-architecture i386 && apt-get update && \
    apt-get install -y --no-install-recommends wine wine32:i386 wine64 \
      xvfb x11-apps x11-utils xauth xdotool imagemagick python3 ca-certificates fonts-dejavu-core procps && \
    rm -rf /var/lib/apt/lists/*
ENV WINEDLLOVERRIDES="mscoree,mshtml=" WINEDEBUG=-all WINEPREFIX=/root/.wine
RUN (Xvfb :99 -screen 0 1280x1024x24 >/dev/null 2>&1 &) && sleep 2 && DISPLAY=:99 wineboot -i >/dev/null 2>&1; DISPLAY=:99 wineserver -w; true
COPY --from=film /film/host_script.swf /opt/fh/host_script.swf
