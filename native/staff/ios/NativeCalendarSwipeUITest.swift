import XCTest

final class NativeCalendarSwipeUITest: XCTestCase {
    func testWeekSwipeMovesColumnsButNotRuler() throws {
        continueAfterFailure = false
        let fixture = try XCTUnwrap(Bundle(for: Self.self).url(forResource: "02b-calendar-week", withExtension: "json"))
        let app = XCUIApplication()
        app.launchEnvironment["APLUS_NATIVE_QA_FIXTURE"] = try Data(contentsOf: fixture).base64EncodedString()
        app.launch()
        let ruler = app.staticTexts["calendar-ruler-time-10"].firstMatch
        XCTAssertTrue(ruler.waitForExistence(timeout: 15))
        let first = app.staticTexts["calendar-column-0"].firstMatch
        XCTAssertTrue(first.waitForExistence(timeout: 8))
        let originalRulerX = ruler.frame.minX
        let originalColumnX = first.frame.minX
        let start = app.coordinate(withNormalizedOffset: CGVector(dx: 0.89, dy: 0.48))
        let end = app.coordinate(withNormalizedOffset: CGVector(dx: 0.23, dy: 0.48))
        start.press(forDuration: 0.08, thenDragTo: end)
        // Wait until the scroll gesture settles. The test is not satisfied by
        // a fixed screenshot: the date column must actually move.
        let moved = NSPredicate { _, _ in !first.exists || abs(first.frame.minX - originalColumnX) > 35 }
        let result = XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: moved, object: nil)], timeout: 5)
        XCTAssertEqual(result, .completed)
        XCTAssertTrue(ruler.exists)
        XCTAssertEqual(ruler.frame.minX, originalRulerX, accuracy: 1)
    }
}
