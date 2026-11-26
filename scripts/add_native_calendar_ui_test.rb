# Add a disposable UI-test target to the generated Capacitor iOS project.
# The app target and packaged binary are unchanged by this QA configuration.
require 'xcodeproj'
project_path = 'ios/App/App.xcodeproj'
project = Xcodeproj::Project.open(project_path)
app = project.targets.find { |target| target.name == 'App' } or abort 'Missing App target'
test = project.new_target(:ui_test_bundle, 'NativeCalendarUITests', :ios, '16.0')
test.add_dependency(app)
test.build_configurations.each do |config|
  config.build_settings.merge!({
    'PRODUCT_BUNDLE_IDENTIFIER' => 'de.aplusesthetic.app.NativeCalendarUITests',
    'PRODUCT_NAME' => 'NativeCalendarUITests',
    'PRODUCT_MODULE_NAME' => 'NativeCalendarUITests',
    'TEST_TARGET_NAME' => 'App',
    'GENERATE_INFOPLIST_FILE' => 'YES',
    'SWIFT_VERSION' => '5.0',
    'TARGETED_DEVICE_FAMILY' => '1,2',
    'IPHONEOS_DEPLOYMENT_TARGET' => '16.0',
    'CODE_SIGNING_ALLOWED' => 'NO'
  })
end
swift = project.main_group.new_file(File.expand_path('native/staff/ios/NativeCalendarSwipeUITest.swift'))
test.add_file_references([swift])
fixture = project.main_group.new_file(File.expand_path('qa-fixtures/02b-calendar-week.json'))
test.resources_build_phase.add_file_reference(fixture, true)
project.save
scheme = Xcodeproj::XCScheme.new
scheme.configure_with_targets(app, test)
scheme.save_as(project_path, 'NativeCalendarSwipeQA', true)
