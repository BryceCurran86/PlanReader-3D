"""Opt-in Linux process-tree network denial for trusted local benchmark code.

Kernel seccomp filters are inherited by subprocesses and cannot be removed.
Not a general hostile-code sandbox; use only trusted code and local files.
"""
import ctypes
import errno
import os
from pathlib import Path
import socket
import sys


def verify_network_denial():
    for fd in Path('/proc/self/fd').iterdir():
        try:
            target = os.readlink(fd)
        except FileNotFoundError:
            continue
        if target.startswith('socket:'):
            raise ValueError('benchmark has an inherited socket descriptor')
    for family in (socket.AF_INET, socket.AF_INET6, socket.AF_UNIX):
        try:
            s = socket.socket(family, socket.SOCK_STREAM)
        except OSError as exc:
            if exc.errno != errno.EPERM:
                raise ValueError('could not verify kernel socket denial') from exc
        else:
            s.close()
            raise ValueError('kernel socket denial is not active')


def install_network_denial():
    if sys.platform != 'linux':
        raise ValueError('process network isolation requires Linux')
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        raise ValueError('original-source benchmark execution is local only')
    for fd in Path('/proc/self/fd').iterdir():
        try:
            target = os.readlink(fd)
        except FileNotFoundError:
            continue
        if target.startswith('socket:'):
            raise ValueError('benchmark has an inherited socket descriptor')
    lib = ctypes.CDLL('libseccomp.so.2', use_errno=True)
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    lib.seccomp_rule_add.restype = ctypes.c_int
    lib.seccomp_attr_set.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint32]
    lib.seccomp_attr_set.restype = ctypes.c_int
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_load.restype = ctypes.c_int
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    ctx = lib.seccomp_init(0x7fff0000)  # SCMP_ACT_ALLOW
    if not ctx:
        raise ValueError('could not allocate seccomp filter')
    if lib.seccomp_attr_set(ctx, 4, 1) != 0:  # SCMP_FLTATR_CTL_TSYNC
        lib.seccomp_release(ctx)
        raise ValueError("could not synchronize kernel filter")
    try:
        for name in ('socket', 'socketpair', 'connect', 'bind', 'listen', 'accept', 'accept4', 'sendto', 'sendmsg', 'sendmmsg', 'recvmsg', 'recvmmsg', 'io_uring_setup', 'io_uring_enter', 'io_uring_register', 'pidfd_getfd', 'ptrace', 'process_vm_writev'):
            nr = lib.seccomp_syscall_resolve_name(name.encode())
            if nr < 0 or lib.seccomp_rule_add(ctx, 0x00050000 | errno.EPERM, nr, 0) != 0:
                raise ValueError('could not configure kernel network denial: ' + name)
        if lib.seccomp_load(ctx) != 0:
            raise ValueError('could not load kernel network denial')
    finally:
        lib.seccomp_release(ctx)
    verify_network_denial()
