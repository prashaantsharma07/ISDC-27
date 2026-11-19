#include "QGCApplication.h"
#include <QtCore/QtEnvironmentVariables>
#include "QGCCommandLineParser.h"
#include "LogManager.h"
#include "QGCLoggingCategory.h"
#include "Platform.h"

#ifdef QGC_UNITTEST_BUILD
    #include "UnitTestList.h"
#endif

QGC_LOGGING_CATEGORY_ON(MainLog, "Main")

int main(int argc, char *argv[])
{
    // --- Parse command line arguments ---
    const auto args = QGCCommandLineParser::parse(argc, argv);
    if (const auto exitCode = QGCCommandLineParser::handleParseResult(args)) {
        return *exitCode;
    }

    // --- Platform initialization ---
    if (const auto exitCode = Platform::initialize(argc, argv, args)) {
        return *exitCode;
    }

    // TeamMARS: Qt Multimedia (used only by the optional camera panels) decodes in software.
    // Its VA-API path swaps red/blue on MJPEG streams on Intel GPUs. QGC's own video uses GStreamer
    // and is not affected. Set QT_FFMPEG_DECODING_HW_DEVICE_TYPES yourself to override.
    if (!qEnvironmentVariableIsSet("QT_FFMPEG_DECODING_HW_DEVICE_TYPES")) {
        qputenv("QT_FFMPEG_DECODING_HW_DEVICE_TYPES", "none");
    }

    QGCApplication app(argc, argv, args);

    LogManager::installHandler(args.logOutput);

    Platform::setupPostApp();

    app.init();

    // Apply after installFilter() (called during app.init) so rules aren't overwritten.
    LogManager::applyEnvironmentLogLevel();

    // --- Run application or tests ---
    const auto run = [&]() -> int {
        using QGCCommandLineParser::AppMode;
        switch (QGCCommandLineParser::determineAppMode(args)) {
#ifdef QGC_UNITTEST_BUILD
        case AppMode::ListTests:
        case AppMode::Test:
            return QGCUnitTest::handleTestOptions(args);
#endif
        case AppMode::BootTest:
            if (!app.bootTestPassed()) {
                qCCritical(MainLog) << "Simple boot test failed";
                return EXIT_FAILURE;
            }
            qCInfo(MainLog) << "Simple boot test completed";
            return EXIT_SUCCESS;
        case AppMode::Gui:
            qCInfo(MainLog) << "Starting application event loop";
            return app.exec();
        }
        Q_UNREACHABLE();
    };

    const int exitCode = run();

    // --- Cleanup ---
    app.shutdown();

    qCInfo(MainLog) << "Exiting main";

    // Destroy LogManager while Qt is still fully functional (before static destruction).
    delete LogManager::instance();

    return exitCode;
}
