# NYC 311 (Socrata `erm2-nwe9`) API Samples

## 1. Status Values (`$select=status,count(*)&$group=status`)

```json
[
  {
    "status": "Assigned",
    "count": "24961"
  },
  {
    "status": "Cancel",
    "count": "1"
  },
  {
    "status": "Closed",
    "count": "22775826"
  },
  {
    "status": "In Progress",
    "count": "294346"
  },
  {
    "status": "Open",
    "count": "101808"
  },
  {
    "status": "Pending",
    "count": "63543"
  },
  {
    "status": "Started",
    "count": "3320"
  },
  {
    "status": "Unspecified",
    "count": "2874"
  }
]
```

## 2. January 2025 Row Count

Query: `created_date >= '2025-01-01T00:00:00' AND created_date < '2025-02-01T00:00:00'`

```json
[
  {
    "count": "348241"
  }
]
```

## 3. Union of Observed Columns (100-row sample)

```json
[
  ":@computed_region_92fq_4b7q",
  ":@computed_region_f5dn_yrer",
  ":@computed_region_sbqj_enih",
  ":@computed_region_yeji_bk3q",
  "address_type",
  "agency",
  "agency_name",
  "bbl",
  "borough",
  "city",
  "closed_date",
  "community_board",
  "complaint_type",
  "council_district",
  "created_date",
  "cross_street_1",
  "cross_street_2",
  "descriptor",
  "descriptor_2",
  "due_date",
  "facility_type",
  "incident_address",
  "incident_zip",
  "intersection_street_1",
  "intersection_street_2",
  "landmark",
  "latitude",
  "location",
  "location_type",
  "longitude",
  "open_data_channel_type",
  "park_borough",
  "park_facility_name",
  "police_precinct",
  "resolution_action_updated_date",
  "resolution_description",
  "status",
  "street_name",
  "taxi_pick_up_location",
  "unique_key",
  "vehicle_type",
  "x_coordinate_state_plane",
  "y_coordinate_state_plane"
]
```

## 4. Sample Records (`$limit=5`)

```json
[
  {
    "unique_key": "71234932",
    "created_date": "2026-11-24T02:06:14.000",
    "agency": "NYPD",
    "agency_name": "New York City Police Department",
    "complaint_type": "Noise - Commercial",
    "descriptor": "Loud Talking",
    "location_type": "Club/Bar/Restaurant",
    "incident_zip": "10014",
    "incident_address": "510 HUDSON STREET",
    "street_name": "HUDSON STREET",
    "cross_street_1": "CHRISTOPHER STREET",
    "cross_street_2": "WEST 10 STREET",
    "intersection_street_1": "CHRISTOPHER STREET",
    "intersection_street_2": "WEST 10 STREET",
    "address_type": "ADDRESS",
    "city": "NEW YORK",
    "landmark": "HUDSON STREET",
    "status": "In Progress",
    "community_board": "02 MANHATTAN",
    "council_district": "03",
    "police_precinct": "Precinct 6",
    "bbl": "1006190005",
    "borough": "MANHATTAN",
    "x_coordinate_state_plane": "982493",
    "y_coordinate_state_plane": "206473",
    "open_data_channel_type": "ONLINE",
    "park_facility_name": "Unspecified",
    "park_borough": "MANHATTAN",
    "latitude": "40.73339717794695",
    "longitude": "-74.0063397120739",
    "location": {
      "type": "Point",
      "coordinates": [
        -74.006339712074,
        40.733397177947
      ]
    },
    ":@computed_region_f5dn_yrer": "57",
    ":@computed_region_yeji_bk3q": "4",
    ":@computed_region_sbqj_enih": "3",
    ":@computed_region_92fq_4b7q": "10"
  },
  {
    "unique_key": "71235909",
    "created_date": "2026-11-24T02:05:40.000",
    "agency": "NYPD",
    "agency_name": "New York City Police Department",
    "complaint_type": "Noise - Vehicle",
    "descriptor": "Car/Truck Music",
    "location_type": "Street/Sidewalk",
    "incident_zip": "11201",
    "incident_address": "8 REMSEN STREET",
    "street_name": "REMSEN STREET",
    "cross_street_1": "BROOKLYN HEIGHTS PROMENADE",
    "cross_street_2": "MONTAGUE TERRACE",
    "intersection_street_1": "BROOKLYN HEIGHTS PROMENADE",
    "intersection_street_2": "MONTAGUE TERRACE",
    "address_type": "ADDRESS",
    "city": "BROOKLYN",
    "landmark": "REMSEN STREET",
    "status": "In Progress",
    "community_board": "02 BROOKLYN",
    "council_district": "33",
    "police_precinct": "Precinct 84",
    "bbl": "3002510006",
    "borough": "BROOKLYN",
    "x_coordinate_state_plane": "984795",
    "y_coordinate_state_plane": "192512",
    "open_data_channel_type": "MOBILE",
    "park_facility_name": "Unspecified",
    "park_borough": "BROOKLYN",
    "vehicle_type": "Car",
    "latitude": "40.695077724850115",
    "longitude": "-73.99803462876274",
    "location": {
      "type": "Point",
      "coordinates": [
        -73.998034628763,
        40.69507772485
      ]
    },
    ":@computed_region_f5dn_yrer": "68",
    ":@computed_region_yeji_bk3q": "2",
    ":@computed_region_sbqj_enih": "54",
    ":@computed_region_92fq_4b7q": "38"
  },
  {
    "unique_key": "71234036",
    "created_date": "2026-11-24T02:05:25.000",
    "agency": "NYPD",
    "agency_name": "New York City Police Department",
    "complaint_type": "Illegal Parking",
    "descriptor": "Commercial Overnight Parking",
    "location_type": "Street/Sidewalk",
    "incident_zip": "11223",
    "incident_address": "2214 MCDONALD AVENUE",
    "street_name": "MCDONALD AVENUE",
    "cross_street_1": "SLOAN PLACE",
    "cross_street_2": "WHITNEY PLACE",
    "intersection_street_1": "SLOAN PLACE",
    "intersection_street_2": "WHITNEY PLACE",
    "address_type": "ADDRESS",
    "city": "BROOKLYN",
    "landmark": "MCDONALD AVENUE",
    "status": "In Progress",
    "community_board": "11 BROOKLYN",
    "council_district": "44",
    "police_precinct": "Precinct 62",
    "bbl": "3071030017",
    "borough": "BROOKLYN",
    "x_coordinate_state_plane": "991732",
    "y_coordinate_state_plane": "157270",
    "open_data_channel_type": "ONLINE",
    "park_facility_name": "Unspecified",
    "park_borough": "BROOKLYN",
    "latitude": "40.598342920298954",
    "longitude": "-73.97305760800359",
    "location": {
      "type": "Point",
      "coordinates": [
        -73.973057608004,
        40.598342920299
      ]
    },
    ":@computed_region_f5dn_yrer": "1",
    ":@computed_region_yeji_bk3q": "2",
    ":@computed_region_sbqj_enih": "37",
    ":@computed_region_92fq_4b7q": "45"
  },
  {
    "unique_key": "71232902",
    "created_date": "2026-11-24T02:05:24.000",
    "agency": "NYPD",
    "agency_name": "New York City Police Department",
    "complaint_type": "Noise - Street/Sidewalk",
    "descriptor": "Loud Music/Party",
    "location_type": "Street/Sidewalk",
    "incident_zip": "10019",
    "incident_address": "100 CENTRAL PARK SOUTH",
    "street_name": "CENTRAL PARK SOUTH",
    "cross_street_1": "AVENUE OF THE AMERICAS",
    "cross_street_2": "CENTRAL PARK EXIT 7 AVENUE",
    "intersection_street_1": "AVENUE OF THE AMERICAS",
    "intersection_street_2": "CENTRAL PARK EXIT 7 AVENUE",
    "address_type": "ADDRESS",
    "city": "NEW YORK",
    "landmark": "CENTRAL PARK SOUTH",
    "status": "In Progress",
    "community_board": "05 MANHATTAN",
    "council_district": "06",
    "police_precinct": "Precinct 18",
    "bbl": "1010117505",
    "borough": "MANHATTAN",
    "x_coordinate_state_plane": "990743",
    "y_coordinate_state_plane": "218280",
    "open_data_channel_type": "ONLINE",
    "park_facility_name": "Unspecified",
    "park_borough": "MANHATTAN",
    "latitude": "40.765802205327844",
    "longitude": "-73.97656017118615",
    "location": {
      "type": "Point",
      "coordinates": [
        -73.976560171186,
        40.765802205328
      ]
    },
    ":@computed_region_f5dn_yrer": "11",
    ":@computed_region_yeji_bk3q": "4",
    ":@computed_region_sbqj_enih": "10",
    ":@computed_region_92fq_4b7q": "51"
  },
  {
    "unique_key": "71232804",
    "created_date": "2026-11-24T02:05:10.000",
    "agency": "NYPD",
    "agency_name": "New York City Police Department",
    "complaint_type": "Noise - Residential",
    "descriptor": "Loud Music/Party",
    "location_type": "Residential Building/House",
    "incident_zip": "10451",
    "incident_address": "300 EAST 143 STREET",
    "street_name": "EAST 143 STREET",
    "cross_street_1": "MORRIS AVENUE",
    "cross_street_2": "ALEXANDER AVENUE",
    "intersection_street_1": "MORRIS AVENUE",
    "intersection_street_2": "ALEXANDER AVENUE",
    "address_type": "ADDRESS",
    "city": "BRONX",
    "landmark": "EAST 143 STREET",
    "status": "In Progress",
    "community_board": "01 BRONX",
    "council_district": "08",
    "police_precinct": "Precinct 40",
    "bbl": "2023250001",
    "borough": "BRONX",
    "x_coordinate_state_plane": "1005298",
    "y_coordinate_state_plane": "236089",
    "open_data_channel_type": "PHONE",
    "park_facility_name": "Unspecified",
    "park_borough": "BRONX",
    "latitude": "40.81466043118502",
    "longitude": "-73.92396060890404",
    "location": {
      "type": "Point",
      "coordinates": [
        -73.923960608904,
        40.814660431185
      ]
    },
    ":@computed_region_f5dn_yrer": "49",
    ":@computed_region_yeji_bk3q": "5",
    ":@computed_region_sbqj_enih": "23",
    ":@computed_region_92fq_4b7q": "35"
  }
]
```
