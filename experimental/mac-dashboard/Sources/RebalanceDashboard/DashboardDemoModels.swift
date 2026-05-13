import Foundation

struct DashboardDemoItem: Identifiable, Hashable, Sendable
{
    enum Kind: String, CaseIterable, Hashable, Sendable
    {
        case service
        case task
        case dataSource
    }

    enum Status: String, Hashable, Sendable
    {
        case healthy
        case warning
        case failed
    }

    let id: UUID
    var name: String
    var summary: String
    var kind: Kind
    var status: Status
    var notes: [String]

    init(
        id: UUID = UUID(),
        name: String,
        summary: String,
        kind: Kind,
        status: Status,
        notes: [String]
    ) {
        self.id = id
        self.name = name
        self.summary = summary
        self.kind = kind
        self.status = status
        self.notes = notes
    }
}

enum DashboardDemoRoute: Hashable, Sendable
{
    case item(UUID)
}

enum DashboardDemoSheet: Hashable, Sendable
{
    case settings
    case maintenance
}

enum DashboardDemoConfirmation: Hashable, Sendable
{
    case removeItem(UUID)
}

enum DashboardDemoPackageSortMode: String, CaseIterable, Hashable, Sendable, Identifiable
{
    case name
    case installDate
    case size

    var id: Self { self }

    var title: String
    {
        switch self
        {
        case .name:
            return "Name"
        case .installDate:
            return "Install Date"
        case .size:
            return "Size"
        }
    }
}

enum DashboardDemoCaveatDisplayMode: String, CaseIterable, Hashable, Sendable, Identifiable
{
    case full
    case compact

    var id: Self { self }

    var title: String
    {
        switch self
        {
        case .full:
            return "Full"
        case .compact:
            return "Compact"
        }
    }
}

enum DashboardDemoOutdatedInfoMode: String, CaseIterable, Hashable, Sendable, Identifiable
{
    case none
    case versionOnly
    case all

    var id: Self { self }

    var title: String
    {
        switch self
        {
        case .none:
            return "None"
        case .versionOnly:
            return "Version Only"
        case .all:
            return "All Details"
        }
    }
}

enum DashboardDemoBackupDateStyle: String, CaseIterable, Hashable, Sendable, Identifiable
{
    case numeric
    case abbreviated
    case long
    case omitted

    var id: Self { self }

    var title: String
    {
        switch self
        {
        case .numeric:
            return "Numeric"
        case .abbreviated:
            return "Abbreviated"
        case .long:
            return "Long"
        case .omitted:
            return "Omitted"
        }
    }

    var dateStyle: Date.FormatStyle.DateStyle
    {
        switch self
        {
        case .numeric:
            return .numeric
        case .abbreviated:
            return .abbreviated
        case .long:
            return .long
        case .omitted:
            return .omitted
        }
    }
}

enum DashboardDemoNotificationDeliveryMode: String, CaseIterable, Hashable, Sendable, Identifiable
{
    case badge
    case banner
    case both
    case none

    var id: Self { self }

    var title: String
    {
        switch self
        {
        case .badge:
            return "Badge"
        case .banner:
            return "Notification"
        case .both:
            return "Both"
        case .none:
            return "None"
        }
    }
}

enum DashboardDemoNotificationAuthorizationState: String, CaseIterable, Hashable, Sendable, Identifiable
{
    case notDetermined
    case denied
    case authorized
    case provisional
    case ephemeral

    var id: Self { self }

    var title: String
    {
        switch self
        {
        case .notDetermined:
            return "Not Determined"
        case .denied:
            return "Denied"
        case .authorized:
            return "Authorized"
        case .provisional:
            return "Provisional"
        case .ephemeral:
            return "Ephemeral"
        }
    }
}

enum DashboardDemoDiscoverabilityDaySpan: String, CaseIterable, Hashable, Sendable, Identifiable
{
    case week
    case month
    case quarter

    var id: Self { self }

    var title: String
    {
        switch self
        {
        case .week:
            return "Last 7 days"
        case .month:
            return "Last 30 days"
        case .quarter:
            return "Last 90 days"
        }
    }
}

enum DashboardDemoTopItemSortMode: String, CaseIterable, Hashable, Sendable, Identifiable
{
    case popularity
    case recency
    case name

    var id: Self { self }

    var title: String
    {
        switch self
        {
        case .popularity:
            return "Popularity"
        case .recency:
            return "Recency"
        case .name:
            return "Name"
        }
    }
}
