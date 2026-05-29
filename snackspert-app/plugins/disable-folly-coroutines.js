const { withDangerousMod } = require('expo/config-plugins');
const fs = require('fs');
const path = require('path');

module.exports = function disableFollyCoroutines(config) {
  return withDangerousMod(config, [
    'ios',
    async (config) => {
      const podfilePath = path.join(config.modRequest.platformProjectRoot, 'Podfile');
      let podfile = fs.readFileSync(podfilePath, 'utf8');

      const snippet = `
  # Disable folly coroutines (Xcode 26 has coroutine support but RN 0.79 folly lacks coro headers)
  post_integrate do |installer|
    installer.pods_project.targets.each do |target|
      target.build_configurations.each do |bc|
        defs = bc.build_settings['GCC_PREPROCESSOR_DEFINITIONS'] || ['$(inherited)']
        defs = [defs] if defs.is_a?(String)
        unless defs.include?('FOLLY_CFG_NO_COROUTINES=1')
          defs << 'FOLLY_CFG_NO_COROUTINES=1'
        end
        bc.build_settings['GCC_PREPROCESSOR_DEFINITIONS'] = defs
      end
    end
  end
`;

      if (!podfile.includes('FOLLY_CFG_NO_COROUTINES')) {
        podfile = podfile.replace(/(post_install\s+do\s+\|installer\|)/, snippet + '\n$1');
        if (!podfile.includes('FOLLY_CFG_NO_COROUTINES')) {
          podfile += '\n' + snippet;
        }
        fs.writeFileSync(podfilePath, podfile);
      }

      return config;
    },
  ]);
};
