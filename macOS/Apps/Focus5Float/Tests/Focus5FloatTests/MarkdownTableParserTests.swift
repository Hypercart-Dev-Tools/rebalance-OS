import XCTest
@testable import Focus5Float

final class MarkdownTableParserTests: XCTestCase {
    func testBasicPipeTableParsesIntoOneTableBlock() {
        let md = """
        | Repo | Status |
        | --- | --- |
        | rebalance-OS | dirty |
        | Focus5Float | clean |
        """
        let blocks = MarkdownTableParser.parse(md)

        XCTAssertEqual(blocks.count, 1)
        guard case .table(let table) = blocks[0] else {
            return XCTFail("expected a single table block, got \(blocks)")
        }
        XCTAssertEqual(table.header, ["Repo", "Status"])
        XCTAssertEqual(table.rows, [["rebalance-OS", "dirty"], ["Focus5Float", "clean"]])
        XCTAssertEqual(table.alignments, [.leading, .leading])
    }

    func testAlignmentMarkersAreParsedPerColumn() {
        let md = """
        | Left | Center | Right |
        | :--- | :---: | ---: |
        | a | b | c |
        """
        let blocks = MarkdownTableParser.parse(md)
        guard case .table(let table) = blocks[0] else { return XCTFail("expected a table block") }
        XCTAssertEqual(table.alignments, [.leading, .center, .trailing])
    }

    func testTableWithoutLeadingOrTrailingPipesStillParses() {
        let md = """
        Repo | Status
        --- | ---
        rebalance-OS | dirty
        """
        let blocks = MarkdownTableParser.parse(md)
        guard case .table(let table) = blocks[0] else { return XCTFail("expected a table block") }
        XCTAssertEqual(table.header, ["Repo", "Status"])
        XCTAssertEqual(table.rows, [["rebalance-OS", "dirty"]])
    }

    func testRaggedDataRowsArePaddedOrTruncatedToHeaderWidth() {
        let md = """
        | A | B | C |
        | --- | --- | --- |
        | one |
        | two | three | four | five |
        """
        let blocks = MarkdownTableParser.parse(md)
        guard case .table(let table) = blocks[0] else { return XCTFail("expected a table block") }
        XCTAssertEqual(table.rows[0], ["one", "", ""])
        XCTAssertEqual(table.rows[1], ["two", "three", "four"])
    }

    func testPlainTextWithNoDelimiterRowIsNotTreatedAsATable() {
        let md = """
        # Heading
        - bullet one
        - bullet two
        Some sentence with a | pipe in it, but no table.
        """
        let blocks = MarkdownTableParser.parse(md)
        XCTAssertTrue(blocks.allSatisfy {
            if case .line = $0 { return true }
            return false
        })
        XCTAssertEqual(blocks.count, md.split(separator: "\n", omittingEmptySubsequences: false).count)
    }

    func testMismatchedColumnCountBetweenHeaderAndDelimiterIsNotATable() {
        let md = """
        | A | B |
        | --- |
        | one | two |
        """
        let blocks = MarkdownTableParser.parse(md)
        XCTAssertTrue(blocks.allSatisfy {
            if case .line = $0 { return true }
            return false
        })
    }

    func testTableSurroundedByOtherContentOnlyConsumesItsOwnLines() {
        let md = """
        # Title

        | A | B |
        | --- | --- |
        | 1 | 2 |

        - trailing bullet
        """
        let blocks = MarkdownTableParser.parse(md)

        let tableBlocks = blocks.compactMap { block -> MarkdownTable? in
            if case .table(let t) = block { return t }
            return nil
        }
        XCTAssertEqual(tableBlocks.count, 1)
        XCTAssertEqual(tableBlocks[0].rows, [["1", "2"]])

        // Non-table lines around it (heading, blank lines, trailing bullet)
        // still pass through untouched as .line blocks.
        let lineBlocks = blocks.compactMap { block -> String? in
            if case .line(let raw) = block { return raw }
            return nil
        }
        XCTAssertEqual(lineBlocks, ["# Title", "", "", "- trailing bullet"])
    }

    func testTableWithNoDataRowsStillParsesHeaderAndAlignments() {
        let md = """
        | Only | Header |
        | --- | --- |
        """
        let blocks = MarkdownTableParser.parse(md)
        guard case .table(let table) = blocks[0] else { return XCTFail("expected a table block") }
        XCTAssertEqual(table.header, ["Only", "Header"])
        XCTAssertTrue(table.rows.isEmpty)
    }
}
