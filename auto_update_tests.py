#!/usr/bin/env python

import os, sys, subprocess, difflib

from scripts.test.support import run_command, split_wast

print '[ processing and updating testcases... ]\n'

for asm in sorted(os.listdir('test')):
  if asm.endswith('.asm.js'):
    for precise in [0, 1, 2]:
      for opts in [1, 0]:
        cmd = [os.path.join('bin', 'asm2wasm'), os.path.join('test', asm)]
        wasm = asm.replace('.asm.js', '.fromasm')
        if not precise:
          cmd += ['--emit-potential-traps', '--ignore-implicit-traps']
          wasm += '.imprecise'
        elif precise == 2:
          cmd += ['--emit-clamped-potential-traps']
          wasm += '.clamp'
        if not opts:
          wasm += '.no-opts'
          if precise:
            cmd += ['-O0'] # test that -O0 does nothing
        else:
          cmd += ['-O']
        if 'debugInfo' in asm:
          cmd += ['-g']
        if precise and opts:
          # test mem init importing
          open('a.mem', 'wb').write(asm)
          cmd += ['--mem-init=a.mem']
          if asm[0] == 'e':
            cmd += ['--mem-base=1024']
        if 'i64' in asm or 'wasm-only' in asm:
          cmd += ['--wasm-only']
        print ' '.join(cmd)
        actual = run_command(cmd)
        with open(os.path.join('test', wasm), 'w') as o: o.write(actual)

for dot_s_dir in ['dot_s', 'llvm_autogenerated']:
  for s in sorted(os.listdir(os.path.join('test', dot_s_dir))):
    if not s.endswith('.s'): continue
    print '..', s
    wasm = s.replace('.s', '.wast')
    full = os.path.join('test', dot_s_dir, s)
    stack_alloc = ['--allocate-stack=1024'] if dot_s_dir == 'llvm_autogenerated' else []
    cmd = [os.path.join('bin', 's2wasm'), full, '--emscripten-glue'] + stack_alloc
    if s.startswith('start_'):
      cmd.append('--start')
    actual = run_command(cmd, stderr=subprocess.PIPE, expected_err='')

    expected_file = os.path.join('test', dot_s_dir, wasm)
    with open(expected_file, 'w') as o: o.write(actual)

'''
for wasm in ['address.wast']:#os.listdir(os.path.join('test', 'spec')):
  if wasm.endswith('.wast'):
    print '..', wasm
    asm = wasm.replace('.wast', '.2asm.js')
    proc = subprocess.Popen([os.path.join('bin', 'wasm2asm'), os.path.join('test', 'spec', wasm)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    actual, err = proc.communicate()
    assert proc.returncode == 0, err
    assert err == '', 'bad err:' + err
    expected_file = os.path.join('test', asm)
    open(expected_file, 'w').write(actual)
'''

for t in sorted(os.listdir(os.path.join('test', 'print'))):
  if t.endswith('.wast'):
    print '..', t
    wasm = os.path.basename(t).replace('.wast', '')
    cmd = [os.path.join('bin', 'wasm-shell'), os.path.join('test', 'print', t), '--print']
    print '    ', ' '.join(cmd)
    actual, err = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
    with open(os.path.join('test', 'print', wasm + '.txt'), 'w') as o: o.write(actual)
    cmd = [os.path.join('bin', 'wasm-shell'), os.path.join('test', 'print', t), '--print-minified']
    print '    ', ' '.join(cmd)
    actual, err = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
    with open(os.path.join('test', 'print', wasm + '.minified.txt'), 'w') as o: o.write(actual)

for t in sorted(os.listdir(os.path.join('test', 'passes'))):
  if t.endswith('.wast'):
    print '..', t
    passname = os.path.basename(t).replace('.wast', '')
    opts = ['-' + passname] if passname.startswith('O') else ['--' + p for p in passname.split('_')]
    t = os.path.join('test', 'passes', t)
    actual = ''
    for module, asserts in split_wast(t):
      assert len(asserts) == 0
      with open('split.wast', 'w') as o: o.write(module)
      cmd = [os.path.join('bin', 'wasm-opt')] + opts + ['split.wast', '--print']
      actual += run_command(cmd)
    with open(os.path.join('test', 'passes', passname + '.txt'), 'w') as o: o.write(actual)

print '\n[ checking wasm-opt -o notation... ]\n'

wast = os.path.join('test', 'hello_world.wast')
cmd = [os.path.join('bin', 'wasm-opt'), wast, '-o', 'a.wast', '-S']
run_command(cmd)
open(wast, 'w').write(open('a.wast').read())

print '\n[ checking binary format testcases... ]\n'

for wast in sorted(os.listdir('test')):
  if wast.endswith('.wast') and not wast in []: # blacklist some known failures
    for debug_info in [0, 1]:
      cmd = [os.path.join('bin', 'wasm-as'), os.path.join('test', wast), '-o', 'a.wasm']
      if debug_info: cmd += ['-g']
      print ' '.join(cmd)
      if os.path.exists('a.wasm'): os.unlink('a.wasm')
      subprocess.check_call(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      assert os.path.exists('a.wasm')

      cmd = [os.path.join('bin', 'wasm-dis'), 'a.wasm', '-o', 'a.wast']
      print ' '.join(cmd)
      if os.path.exists('a.wast'): os.unlink('a.wast')
      subprocess.check_call(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      assert os.path.exists('a.wast')
      actual = open('a.wast').read()
      binary_name = wast + '.fromBinary'
      if not debug_info: binary_name += '.noDebugInfo'
      with open(os.path.join('test', binary_name), 'w') as o: o.write(actual)

print '\n[ checking example testcases... ]\n'

for t in sorted(os.listdir(os.path.join('test', 'example'))):
  output_file = os.path.join('bin', 'example')
  cmd = ['-Isrc', '-g', '-lasmjs', '-lsupport', '-Llib/.', '-pthread', '-o', output_file]
  if t.endswith('.txt'):
    # check if there is a trace in the file, if so, we should build it
    out = subprocess.Popen([os.path.join('scripts', 'clean_c_api_trace.py'), os.path.join('test', 'example', t)], stdout=subprocess.PIPE).communicate()[0]
    if len(out) == 0:
      print '  (no trace in ', t, ')'
      continue
    print '  (will check trace in ', t, ')'
    src = 'trace.cpp'
    with open(src, 'w') as o: o.write(out)
    expected = os.path.join('test', 'example', t + '.txt')
  else:
    src = os.path.join('test', 'example', t)
    expected = os.path.join('test', 'example', '.'.join(t.split('.')[:-1]) + '.txt')
  if src.endswith(('.c', '.cpp')):
    # build the C file separately
    extra = [os.environ.get('CC') or 'gcc',
             src, '-c', '-o', 'example.o',
             '-Isrc', '-g', '-Llib/.', '-pthread']
    print 'build: ', ' '.join(extra)
    subprocess.check_call(extra)
    # Link against the binaryen C library DSO, using an executable-relative rpath
    cmd = ['example.o', '-lbinaryen'] + cmd + ['-Wl,-rpath=$ORIGIN/../lib']
  else:
    continue
  print '  ', t, src, expected
  if os.environ.get('COMPILER_FLAGS'):
    for f in os.environ.get('COMPILER_FLAGS').split(' '):
      cmd.append(f)
  cmd = [os.environ.get('CXX') or 'g++', '-std=c++11'] + cmd
  try:
    print 'link: ', ' '.join(cmd)
    subprocess.check_call(cmd)
    print 'run...', output_file
    proc = subprocess.Popen([output_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    actual, err = proc.communicate()
    assert proc.returncode == 0, [proc.returncode, actual, err]
    with open(expected, 'w') as o: o.write(actual)
  finally:
    os.remove(output_file)
    if sys.platform == 'darwin':
      # Also removes debug directory produced on Mac OS
      shutil.rmtree(output_file + '.dSYM')

print '\n[ checking wasm-opt testcases... ]\n'

for t in os.listdir('test'):
  if t.endswith('.wast') and not t.startswith('spec'):
    print '..', t
    t = os.path.join('test', t)
    f = t + '.from-wast'
    cmd = [os.path.join('bin', 'wasm-opt'), t, '--print']
    actual = run_command(cmd)
    actual = actual.replace('printing before:\n', '')
    open(f, 'w').write(actual)

print '\n[ checking wasm-dis on provided binaries... ]\n'

for t in os.listdir('test'):
  if t.endswith('.wasm') and not t.startswith('spec'):
    print '..', t
    t = os.path.join('test', t)
    cmd = [os.path.join('bin', 'wasm-dis'), t]
    actual = run_command(cmd)

    open(t + '.fromBinary', 'w').write(actual)

print '\n[ checking wasm-merge... ]\n'

for t in os.listdir(os.path.join('test', 'merge')):
  if t.endswith(('.wast', '.wasm')):
    print '..', t
    t = os.path.join('test', 'merge', t)
    u = t + '.toMerge'
    for finalize in [0, 1]:
      for opt in [0, 1]:
        cmd = [os.path.join('bin', 'wasm-merge'), t, u, '-o', 'a.wast', '-S', '--verbose']
        if finalize: cmd += ['--finalize-memory-base=1024', '--finalize-table-base=8']
        if opt: cmd += ['-O']
        stdout = run_command(cmd)
        actual = open('a.wast').read()
        out = t + '.combined'
        if finalize: out += '.finalized'
        if opt: out += '.opt'
        with open(out, 'w') as o: o.write(actual)
        with open(out + '.stdout', 'w') as o: o.write(stdout)

print '\n[ checking binaryen.js testcases... ]\n'

for s in sorted(os.listdir(os.path.join('test', 'binaryen.js'))):
  if not s.endswith('.js'): continue
  print s
  f = open('a.js', 'w')
  f.write(open(os.path.join('bin', 'binaryen.js')).read())
  f.write(open(os.path.join('test', 'binaryen.js', s)).read())
  f.close()
  cmd = ['mozjs', 'a.js']
  out = run_command(cmd, stderr=subprocess.STDOUT)
  open(os.path.join('test', 'binaryen.js', s + '.txt'), 'w').write(out)

print '\n[ success! ]'
