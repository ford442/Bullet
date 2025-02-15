#!/usr/bin/python

import os, sys, re, json, shutil
from subprocess import Popen, PIPE, STDOUT

# Definitions

INCLUDES = ['btBulletDynamicsCommon.h', os.path.join('BulletCollision', 'CollisionShapes', 'btHeightfieldTerrainShape.h'), os.path.join('BulletCollision', 'CollisionDispatch', 'btGhostObject.h'), os.path.join('BulletDynamics', 'Character', 'btKinematicCharacterController.h')]

# Startup

exec(open(os.path.expanduser('~/.emscripten'), 'r').read())

try:
  EMSCRIPTEN_ROOT
except:
  print "ERROR: Missing EMSCRIPTEN_ROOT (which should be equal to emscripten's root dir) in ~/.emscripten"
  sys.exit(1)

sys.path.append(EMSCRIPTEN_ROOT)
import tools.shared as emscripten

# Settings

'''
          Settings.INLINING_LIMIT = 0
          Settings.DOUBLE_MODE = 0
          Settings.PRECISE_I64_MATH = 0
          Settings.CORRECT_SIGNS = 0
          Settings.CORRECT_OVERFLOWS = 0
          Settings.CORRECT_ROUNDINGS = 0
'''
emcc_args = sys.argv[1:] or '-O3 --flto=thin -s NO_EXIT_RUNTIME=1 -s AGGRESSIVE_VARIABLE_ELIMINATION=1 -s NO_DYNAMIC_EXECUTION=1 -s FILESYSTEM=0'.split(' ')

emcc_args += ['-s', 'TOTAL_MEMORY=%d' % (1400*1024*1024)] # default 64MB. Compile with ALLOW_MEMORY_GROWTH if you want a growable heap (slower though).
#emcc_args += ['-s', 'ALLOW_MEMORY_GROWTH=1'] # resizable heap, with some amount of slowness

emcc_args += '-s EXPORT_NAME="AmmoLib" -s MODULARIZE=1'.split(' ')

print
print '--------------------------------------------------'
print 'Building ammo.js, build type:', emcc_args
print '--------------------------------------------------'
print

'''
import os, sys, re

infile = open(sys.argv[1], 'r').read()
outfile = open(sys.argv[2], 'w')

t1 = infile
while True:
  t2 = re.sub(r'\(\n?!\n?1\n?\+\n?\(\n?!\n?1\n?\+\n?(\w)\n?\)\n?\)', lambda m: '(!1+' + m.group(1) + ')', t1)
  print len(infile), len(t2)
  if t1 == t2: break
  t1 = t2

outfile.write(t2)
'''

# Utilities

stage_counter = 0
def stage(text):
  global stage_counter
  stage_counter += 1
  text = 'Stage %d: %s' % (stage_counter, text)
  print
  print '=' * len(text)
  print text
  print '=' * len(text)
  print

# Main

try:
  this_dir = os.getcwd()
  os.chdir('bullet')
  if not os.path.exists('build'):
    os.makedirs('build')
  os.chdir('build')

  stage('Generate bindings')

  Popen([emscripten.PYTHON, os.path.join(EMSCRIPTEN_ROOT, 'tools', 'webidl_binder.py'), os.path.join(this_dir, 'ammo.idl'), 'glue']).communicate()
  assert os.path.exists('glue.js')
  assert os.path.exists('glue.cpp')

  stage('Build bindings')

  args = ['-I../src', '-c']
  for include in INCLUDES:
    args += ['-include', include]
  emscripten.Building.emcc('glue.cpp', args, 'glue.bc')
  assert(os.path.exists('glue.bc'))

  # Configure with CMake on Windows, and with configure on Unix.
  cmake_build = emscripten.WINDOWS

  if cmake_build:
    if not os.path.exists('CMakeCache.txt'):
      stage('Configure via CMake')
      emscripten.Building.configure([emscripten.PYTHON, os.path.join(EMSCRIPTEN_ROOT, 'emcmake'), 'cmake', '..', '-DBUILD_DEMOS=OFF', '-DBUILD_EXTRAS=OFF', '-DBUILD_CPU_DEMOS=OFF', '-DUSE_GLUT=OFF', '-DCMAKE_BUILD_TYPE=Release'])
  else:
    if not os.path.exists('config.h'):
      stage('Configure (if this fails, run autogen.sh in bullet/ first)')
      emscripten.Building.configure(['../configure', '--disable-demos','--disable-dependency-tracking'])

  stage('Make')

  if emscripten.WINDOWS:
    emscripten.Building.make(['mingw32-make', '-j'])
  else:
    emscripten.Building.make(['make', '-j'])

  stage('Link')

  if cmake_build:
    bullet_libs = [os.path.join('src', 'BulletDynamics', 'libBulletDynamics.a'),
                   os.path.join('src', 'BulletCollision', 'libBulletCollision.a'),
                   os.path.join('src', 'LinearMath', 'libLinearMath.a')]
  else:
    bullet_libs = [os.path.join('src', '.libs', 'libBulletDynamics.a'),
                   os.path.join('src', '.libs', 'libBulletCollision.a'),
                   os.path.join('src', '.libs', 'libLinearMath.a')]

  emscripten.Building.link(['glue.bc'] + bullet_libs, 'libbullet.bc')
  assert os.path.exists('libbullet.bc')

  stage('emcc: ' + ' '.join(emcc_args))

  temp = os.path.join('..', '..', 'builds', 'temp.js')
  emscripten.Building.emcc('libbullet.bc', emcc_args + ['--js-transform', 'python %s' % os.path.join('..', '..', 'bundle.py')],
                           temp)

  assert os.path.exists(temp), 'Failed to create script code'

  stage('wrap')

  wrapped = '''
// This is ammo.js, a port of Bullet Physics to JavaScript. zlib licensed.
''' + open(temp).read() + '''
Ammo = AmmoLib();
'''

  open(temp, 'w').write(wrapped)

finally:
  os.chdir(this_dir);
