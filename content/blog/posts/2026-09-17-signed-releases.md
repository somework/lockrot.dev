---
draft: true
date: 2026-09-17
authors: [igor]
categories: [Releases]
slug: signed-releases
description: What lockrot 0.5.0 signs, what each check proves, and why self-update still trusts a checksum.
---

# What a signed PHAR actually proves

lockrot 0.5.0 is the first release that ships `lockrot.phar.asc` next to the archive, together with
a GitHub build-provenance attestation. Three checks, three different questions.

<!-- more -->

## The checksum

`sha256sum -c lockrot.phar.sha256` proves the archive matches the checksum file next to it. Both
come from the same release, so it proves the download arrived intact — not who published it.

## The signature

`gpg --verify lockrot.phar.asc lockrot.phar` proves the bytes were signed with the lockrot release
key. The release workflow verifies its own signature against the public key committed in the
repository before it uploads anything, so the key on the keyservers and the key in CI cannot drift
apart unnoticed.

## The attestation

`gh attestation verify lockrot.phar --repo somework/lockrot` proves this exact archive was built by
the `PHAR` workflow of `somework/lockrot` from a given commit. No key of lockrot's is involved: the
trust root is GitHub's Sigstore instance.

## Why `self-update` still checks the checksum only

_Draft. Continue here: the update path runs inside PHP without gpg; Composer's answer is an openssl
signature with an embedded public key; what it would take and what it would not add._
