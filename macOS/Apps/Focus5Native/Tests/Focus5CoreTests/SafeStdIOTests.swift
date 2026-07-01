import XCTest
import Darwin
@testable import Focus5Core

final class SafeStdIOTests: XCTestCase {
    override class func setUp() {
        super.setUp()
        SafeStdIO.installSignalHandling()
    }

    func testWriteLineReturnsFalseForBrokenPipe() {
        var fileDescriptors: [Int32] = [0, 0]
        XCTAssertEqual(pipe(&fileDescriptors), 0)
        defer { _ = close(fileDescriptors[1]) }

        XCTAssertEqual(close(fileDescriptors[0]), 0)
        errno = 0

        XCTAssertFalse(SafeStdIO.writeLine("hello", to: fileDescriptors[1]))
        XCTAssertEqual(errno, EPIPE)
    }

    func testWriteLineEmitsUtf8WithTrailingNewline() throws {
        var fileDescriptors: [Int32] = [0, 0]
        XCTAssertEqual(pipe(&fileDescriptors), 0)
        defer {
            _ = close(fileDescriptors[0])
            _ = close(fileDescriptors[1])
        }

        XCTAssertTrue(SafeStdIO.writeLine("hello", to: fileDescriptors[1]))
        XCTAssertEqual(close(fileDescriptors[1]), 0)
        fileDescriptors[1] = -1

        var buffer = [UInt8](repeating: 0, count: 32)
        let count = read(fileDescriptors[0], &buffer, buffer.count)
        XCTAssertEqual(count, 6)
        XCTAssertEqual(String(decoding: buffer.prefix(Int(count)), as: UTF8.self), "hello\n")
    }
}