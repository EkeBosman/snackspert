const { withDangerousMod } = require('expo/config-plugins');
const fs = require('fs');
const path = require('path');

module.exports = function disableFollyCoroutines(config) {
  return withDangerousMod(config, [
    'ios',
    async (config) => {
      const podfilePath = path.join(config.modRequest.platformProjectRoot, 'Podfile');
      let podfile = fs.readFileSync(podfilePath, 'utf8');

      // Code to inject INSIDE the existing post_install block (not a separate hook).
      // post_install runs BEFORE CocoaPods writes the project, so changes are saved.
      const innerCode = [
        '    # Disable folly coroutines (Xcode 26 reports C++20 coro support but RN 0.79 folly lacks coro headers)',
        '    installer.pods_project.targets.each do |target|',
        '      target.build_configurations.each do |bc|',
        '        defs = bc.build_settings[\'GCC_PREPROCESSOR_DEFINITIONS\'] || [\'$(inherited)\']',
        '        defs = [defs] if defs.is_a?(String)',
        '        unless defs.include?(\'FOLLY_CFG_NO_COROUTINES=1\')',
        '          defs << \'FOLLY_CFG_NO_COROUTINES=1\'',
        '        end',
        '        bc.build_settings[\'GCC_PREPROCESSOR_DEFINITIONS\'] = defs',
        '      end',
        '    end',
      ].join('\n');

      if (!podfile.includes('FOLLY_CFG_NO_COROUTINES')) {
        const replaced = podfile.replace(
          /(post_install\s+do\s+\|installer\|)/,
          '$1\n' + innerCode
        );

        if (replaced !== podfile) {
          podfile = replaced;
        } else {
          // No post_install block found — wrap in a standalone one
          podfile += '\npost_install do |installer|\n' + innerCode + '\nend\n';
        }

        fs.writeFileSync(podfilePath, podfile);
      }

      return config;
    },
  ]);
};
