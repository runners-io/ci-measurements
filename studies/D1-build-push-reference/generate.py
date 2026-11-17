#!/usr/bin/env python3
"""Writes the D1 workflows and the snippets the post prints from one table, so what ran is what is printed.

snippets/<name>.yml   the workflow as the post prints it (action tags, `on: push`)
../../.github/workflows/D1-<name>.yml   the same steps, pinned to commits, with the proof added (workflow_dispatch)
"""
import pathlib

HERE = pathlib.Path(__file__).parent
WF = HERE.parent.parent / ".github" / "workflows"

PIN = {
    "actions/checkout@v7": "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
    "docker/login-action@v4": "docker/login-action@8aa5831fb8d48d8f76594c7ddde61ae58019f550 # v4",
    "docker/setup-buildx-action@v4": "docker/setup-buildx-action@f87e5991a6d7451dcb8d9637bfbc97413f497069 # v4.4.1",
    "docker/build-push-action@v7": "docker/build-push-action@c3c9e263c25d99ce0380d002d59b67737d91b0dc # v7.4.0",
    "docker/setup-qemu-action@v4": "docker/setup-qemu-action@{QEMU} # v4.x",
    "actions/cache@v6": "actions/cache@55cc8345863c7cc4c66a329aec7e433d2d1c52a9 # v6.1.0",
}

LOGIN = """      - uses: docker/login-action@v4
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
"""
CHECKOUT = "      - uses: actions/checkout@v7\n"
BUILDX = "      - uses: docker/setup-buildx-action@v4\n"

def build(extra_with: str, tags="ghcr.io/${{ github.repository }}:latest", platforms=None, setup_with=""):
    s = ""
    return s

# name -> dict(pre=steps before setup-buildx, setup=buildx step, build=build step, tag, proof pre-steps)
TYPES = {}

TYPES["gha"] = dict(
    title="type=gha",
    pre="",
    setup=BUILDX,
    build="""      - uses: docker/build-push-action@v7
        with:
          context: studies/D1-build-push-reference
          push: true
          tags: ghcr.io/${{ github.repository }}:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
""",
)
TYPES["registry"] = dict(
    title="type=registry",
    pre="",
    setup=BUILDX,
    build="""      - uses: docker/build-push-action@v7
        with:
          context: studies/D1-build-push-reference
          push: true
          tags: ghcr.io/${{ github.repository }}:latest
          cache-from: type=registry,ref=ghcr.io/${{ github.repository }}:buildcache
          cache-to: type=registry,ref=ghcr.io/${{ github.repository }}:buildcache,mode=max
""",
)
TYPES["inline"] = dict(
    title="type=inline",
    pre="",
    setup=BUILDX,
    build="""      - uses: docker/build-push-action@v7
        with:
          context: studies/D1-build-push-reference
          push: true
          tags: ghcr.io/${{ github.repository }}:latest
          cache-from: type=registry,ref=ghcr.io/${{ github.repository }}:latest
          cache-to: type=inline
""",
)
TYPES["local"] = dict(
    title="type=local",
    pre="""      - uses: actions/cache@v6
        with:
          path: ${{ runner.temp }}/.buildx-cache
          key: ${{ runner.os }}-buildx-${{ github.sha }}
          restore-keys: |
            ${{ runner.os }}-buildx-
""",
    setup=BUILDX,
    build="""      - uses: docker/build-push-action@v7
        with:
          context: studies/D1-build-push-reference
          push: true
          tags: ghcr.io/${{ github.repository }}:latest
          cache-from: type=local,src=${{ runner.temp }}/.buildx-cache
          cache-to: type=local,dest=${{ runner.temp }}/.buildx-cache,mode=max
""",
)
TYPES["s3"] = dict(
    title="type=s3",
    pre="""      - name: Start MinIO, an S3-compatible server, and make a bucket
        run: |
          docker run -d --name minio --network host -e MINIO_ROOT_USER=d1access -e MINIO_ROOT_PASSWORD=d1secret-d1secret minio/minio server /data
          docker run --rm --network host --entrypoint sh minio/mc -c 'until mc alias set d1 http://127.0.0.1:9000 d1access d1secret-d1secret; do sleep 1; done; mc mb d1/buildcache'
""",
    setup="""      - uses: docker/setup-buildx-action@v4
        with:
          driver-opts: network=host
""",
    build="""      - uses: docker/build-push-action@v7
        with:
          context: studies/D1-build-push-reference
          push: true
          tags: ghcr.io/${{ github.repository }}:latest
          cache-from: type=s3,region=us-east-1,bucket=buildcache,name=app,endpoint_url=http://127.0.0.1:9000,use_path_style=true,access_key_id=d1access,secret_access_key=d1secret-d1secret
          cache-to: type=s3,region=us-east-1,bucket=buildcache,name=app,endpoint_url=http://127.0.0.1:9000,use_path_style=true,access_key_id=d1access,secret_access_key=d1secret-d1secret,mode=max
""",
)
TYPES["azblob"] = dict(
    title="type=azblob",
    pre="""      - name: Start Azurite, the Azure Storage emulator
        run: |
          docker run -d --name azurite --network host mcr.microsoft.com/azure-storage/azurite azurite-blob --blobHost 127.0.0.1 --skipApiVersionCheck
""",
    setup="""      - uses: docker/setup-buildx-action@v4
        with:
          driver-opts: network=host
""",
    build="""      - uses: docker/build-push-action@v7
        with:
          context: studies/D1-build-push-reference
          push: true
          tags: ghcr.io/${{ github.repository }}:latest
          cache-from: type=azblob,account_url=http://127.0.0.1:10000/devstoreaccount1,account_name=devstoreaccount1,container=buildcache,name=app,secret_access_key=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==
          cache-to: type=azblob,account_url=http://127.0.0.1:10000/devstoreaccount1,account_name=devstoreaccount1,container=buildcache,name=app,secret_access_key=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==,mode=max
""",
)

def pin(text: str) -> str:
    for k, v in PIN.items():
        text = text.replace(k, v)
    return text

def snippet(t):
    return (
        "name: ci\n\non:\n  push:\n\njobs:\n  docker:\n    runs-on: ubuntu-24.04\n    permissions:\n      contents: read\n      packages: write\n    steps:\n"
        + CHECKOUT + LOGIN + t["pre"] + t["setup"] + t["build"]
    )

def harness(name, t):
    # The only text the harness changes in a printed step: tags are made unique per workflow, so six runs at once do
    # not push to one tag. The cache lines are otherwise the printed ones.
    t = dict(t)
    for k in ("pre", "setup", "build"):
        t[k] = t[k].replace(":latest", f":d1-{name}").replace(":buildcache", f":d1-{name}-buildcache")
    # Two builds on two fresh builders in one job. The second must read what the first wrote: /stamp, written by
    # `RUN date`, is the same in both images only if the RUN layer came from the cache.
    reset = """      - name: Remove the builder and everything it held, as a new runner would
        run: |
          docker buildx rm --force --all-inactive || true
          for b in $(docker buildx ls --format '{{.Name}}' | grep -v -x -e default -e desktop-linux || true); do docker buildx rm --force "$b" || true; done
          docker system prune --all --force >/dev/null
"""
    read = """      - name: Read /stamp from the image just pushed
        id: {id}
        run: echo "stamp=$(docker run --rm ghcr.io/${{{{ github.repository }}}}:d1-{name})" >> "$GITHUB_OUTPUT"
"""
    # an image pull under the same tag would reuse a local copy; the prune above removes it
    first = t["setup"] + t["build"] + read.format(id="first", name=name)
    second = t["setup"] + t["build"] + read.format(id="second", name=name)
    empty = ""
    if name in ("registry", "inline"):
        ref = f"d1-{name}-buildcache" if name == "registry" else f"d1-{name}"
        empty = f"""      - name: The cache must start empty
        run: |
          if docker buildx imagetools inspect ghcr.io/${{{{ github.repository }}}}:{ref} >/dev/null 2>&1; then
            echo "::error::ghcr.io/${{{{ github.repository }}}}:{ref} exists before the first build; delete it and run again"; exit 1
          fi
"""
    if name == "gha":
        empty = """      - name: The cache must start empty
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          n=$(gh cache list --repo "$GITHUB_REPOSITORY" --limit 100 --json key --jq '[.[] | select(.key | contains("buildkit"))] | length')
          echo "buildkit cache entries before the first build: $n"
          [ "$n" = "0" ] || { echo "::error::the gha cache is not empty; delete it and run again"; exit 1; }
"""
    compare = """      - name: The second build must have read the first one's cache
        run: |
          echo "first : ${{ steps.first.outputs.stamp }}"
          echo "second: ${{ steps.second.outputs.stamp }}"
          [ -n "${{ steps.first.outputs.stamp }}" ] && [ "${{ steps.first.outputs.stamp }}" = "${{ steps.second.outputs.stamp }}" ]
"""
    pre = t["pre"]
    body = (
        f"name: D1 · {t['title']}\n"
        "# Study D1: the workflow printed on the post, plus a second build on a fresh builder. The two images carry the same\n"
        "# /stamp only if the second build took the RUN layer from the cache. See studies/D1-build-push-reference/METHOD.md.\n"
        "on:\n  workflow_dispatch:\n\npermissions:\n  contents: read\n\njobs:\n  docker:\n    runs-on: ubuntu-24.04\n    timeout-minutes: 30\n    permissions:\n      contents: read\n      packages: write\n      actions: read\n    steps:\n"
        + CHECKOUT + LOGIN + empty + pre + first + reset + second + compare
    )
    return body

for name, t in TYPES.items():
    (HERE / "snippets" / f"{name}.yml").write_text(snippet(t))
    (WF / f"D1-cache-{name}.yml").write_text(pin(harness(name, t)))
print("wrote", len(TYPES), "snippets and workflows")
