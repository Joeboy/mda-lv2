#!/usr/bin/env python
import os
import re
import shutil
import sys
import waflib.extras.autowaf as autowaf

MDA_VERSION = '1.1.0'

# Mandatory waf variables
APPNAME = 'MDA'        # Package name for waf dist
VERSION = MDA_VERSION  # Package version for waf dist
top     = '.'          # Source directory
out     = 'build'      # Build directory

def options(opt):
    opt.load('compiler_cxx')
    autowaf.set_options(opt)
    opt.add_option('--picolv2', action='store_true', default=False, dest='picolv2',
                   help='Build plugins for the PicoLV2 target')
    opt.add_option('--epiano-decimation', type='int', default=1, dest='epiano_decimation',
                   help='Keep every Nth EPiano PCM sample (1, 2, 3, or 4; default: 1)')
    opt.add_option('--piano-decimation', type='int', default=1, dest='piano_decimation',
                   help='Keep every Nth Piano PCM sample (1, 2, 3, or 4; default: 1)')

def configure(conf):
    is_pico = getattr(conf.options, 'picolv2', False)
    decimations = {
        'EPiano': conf.options.epiano_decimation,
        'Piano': conf.options.piano_decimation,
    }
    for plugin, decimation in decimations.items():
        if decimation not in (1, 2, 3, 4):
            conf.fatal('--%s-decimation must be 1, 2, 3, or 4' % plugin.lower())
    conf.env['PICOLV2'] = is_pico
    conf.env['EPIANO_DECIMATION'] = str(decimations['EPiano'])
    conf.env['PIANO_DECIMATION'] = str(decimations['Piano'])
    if is_pico:
        os.environ['CXX'] = 'arm-none-eabi-g++'
        os.environ['CC'] = 'arm-none-eabi-gcc'
        os.environ['AR'] = 'arm-none-eabi-ar'
        conf.env['CXX'] = ['arm-none-eabi-g++']
        conf.env['CC'] = ['arm-none-eabi-gcc']
        conf.env['AR'] = ['arm-none-eabi-ar']

    conf.load('compiler_cxx')
    autowaf.configure(conf)
    conf.line_just = 23
    autowaf.display_header('MDA.lv2 Configuration')

    autowaf.check_pkg(conf, 'lv2', atleast_version='1.0.0', uselib_store='LV2')

    autowaf.display_msg(conf, "LV2 bundle directory",
                        conf.env.LV2DIR)
    print('')

def build(bld):
    # Make a pattern for shared objects without the 'lib' prefix
    module_pat = re.sub('^lib', '', bld.env.cxxshlib_PATTERN)
    module_ext = module_pat[module_pat.rfind('.'):]
    bld.add_group('sample_data')
    generated_dir = bld.path.get_bld().make_node('generated')
    generator = bld.path.find_resource('scripts/resample_samples.py').abspath()
    sample_data = {
        'EPiano': ('mdaEPianoData.h', 'mdaEPianoData.generated.h', 'EPIANO_DECIMATION'),
        'Piano': ('mdaPianoData.h', 'mdaPianoData.generated.h', 'PIANO_DECIMATION'),
    }
    generated_headers = {}
    for plugin, (source_name, generated_name, decimation_env) in sample_data.items():
        generated_headers[plugin] = generated_dir.make_node(generated_name)
        bld(
            rule='"%s" "%s" ${SRC} ${TGT} %s' %
                 (sys.executable, generator, bld.env[decimation_env]),
            source='src/%s' % source_name,
            target=generated_headers[plugin])
    bld.add_group('plugins')

    plugins = '''
            Ambience
            Bandisto
            BeatBox
            Combo
            DX10
            DeEss
            Degrade
            Delay
            Detune
            Dither
            DubDelay
            Dynamics
            EPiano
            Image
            JX10
            Leslie
            Limiter
            Loudness
            MultiBand
            Overdrive
            Piano
            RePsycho
            RezFilter
            RingMod
            RoundPan
            Shepard
            Splitter
            Stereo
            SubSynth
            TalkBox
            TestTone
            ThruZero
            Tracker
            Transient
            VocInput
            Vocoder
    '''.split()
    for p in plugins:
        bundle = 'mod-mda-%s.lv2' % p

        # Build manifest by substitution
        bld(features     = 'subst',
            source       = 'bundles/%s/manifest.ttl.in' % bundle,
            target       = bld.path.get_bld().make_node('%s/manifest.ttl' % bundle),
            LIB_EXT      = module_ext,
            install_path = '${LV2DIR}/%s' % bundle)

        # Build plugin library
        source = ['src/mda%s.cpp' % p, 'lvz/wrapper.cpp']
        includes = ['.', './lvz', './src']
        if p in generated_headers:
            includes += [generated_dir]
        if bld.env['PICOLV2']:
            source += ['picolv2-runtime.cpp']
        defines = ['PLUGIN_CLASS=mda%s' % p,
                   'URI_PREFIX="http://moddevices.com/plugins/mda/"',
                   'PLUGIN_URI_SUFFIX="%s"' % p,
                   'PLUGIN_HEADER="src/mda%s.h"' % p]
        if p in sample_data:
            defines.append('%s_SAMPLE_DECIMATION=%s' %
                           (p.upper(), bld.env[sample_data[p][2]]))
        obj = bld(features     = 'cxx cxxshlib',
                  source       = source,
                  includes     = includes,
                  name         = p,
                  target       = os.path.join(bundle, p),
                  install_path = '${LV2DIR}/' + bundle,
                  defines      = defines)
        if bld.env['PICOLV2']:
            obj.cxxflags = [
                '-mcpu=cortex-m33', '-mthumb', '-mfloat-abi=hard', '-mfpu=fpv5-sp-d16',
                '-fPIC', '-fno-exceptions', '-fno-rtti', '-fno-use-cxa-atexit',
                '-Wall', '-Wextra', '-O2', '-DPICOLV2', '-idirafter', '/usr/include'
            ]
            obj.linkflags = [
                '-mcpu=cortex-m33', '-mthumb', '-mfloat-abi=hard', '-mfpu=fpv5-sp-d16',
                '-shared', '-nostdlib', '-Wl,-Bsymbolic', '-Wl,-z,undefs',
                '-Wl,-z,max-page-size=0x1000', '-Wl,--no-warnings', '-Wl,-s'
            ]
            obj.env.append_value('LDFLAGS', [
                '-Wl,--start-group', '-lgcc', '-lc', '-lm', '-lnosys', '-Wl,--end-group'
            ])
        else:
            obj.uselib = ['LV2']
        obj.env.cxxshlib_PATTERN = module_pat
        obj.env.SHLIB_MARKER = ''
        obj.env.STLIB_MARKER = ''

        # Set extra files for install
        for i in bld.path.ant_glob('bundles/%s/*.ttl' % bundle):
            bld(features     = 'subst',
                is_copy      = True,
                source       = i,
                target       = bld.path.get_bld().make_node('%s/%s' % (bundle, i.name)),
                install_path = '${LV2DIR}/%s' % bundle)

