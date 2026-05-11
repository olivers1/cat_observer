<?php
# login credentials hidden as global variables
$conn = new mysqli(getenv('DB_HOST'), getenv('DB_USER'), getenv('DB_PASS'), getenv('DB_NAME'));

if ($conn->connect_errno) {
    http_response_code(500);
    exit("DB connection failed");
}

# fetch all rows of the database
$queryAll = "
    SELECT timestamp, movement_direction 
    FROM observations 
    ORDER BY timestamp DESC";
    #WHERE movement_direction = 'ENTRY' OR movement_direction = 'EXIT'
$result = $conn->query($queryAll);

$data = [];
if ($result && $result->num_rows > 0) {
    $data = $result->fetch_all(MYSQLI_ASSOC);
}

# count number of 'EXIT' and store it as number of excursions
$queryExcursions = "
    SELECT COUNT(*) AS excursions
    FROM observations
    WHERE movement_direction = 'EXIT'
";
$resultExcursions = $conn->query($queryExcursions);

$excursions = 0;
if ($resultExcursions) {
    $row = $resultExcursions->fetch_assoc();
    $excursions = (int) $row['excursions'];
}

# fetch rows where movement_direction equals 'ENTRY' and 'EXIT'
$queryLocationStatus = "
    SELECT timestamp, movement_direction
    FROM observations 
    WHERE movement_direction = 'ENTRY' OR movement_direction = 'EXIT'
    ORDER BY timestamp DESC 
    LIMIT 1
";
$resultLocationStatus = $conn->query($queryLocationStatus);

$locationStatus = 'Unknown'; // default value
$statusUpdated = null;
if ($resultLocationStatus && $resultLocationStatus->num_rows > 0) {
    $latestRow = $resultLocationStatus->fetch_assoc();

    // Determine location status and when it was updated
    $direction = strtoupper(trim($latestRow['movement_direction']));
    if ($direction === 'EXIT') {
        $locationStatus = 'Outside';
    } elseif ($direction === 'ENTRY') {
        $locationStatus = 'Inside';
    }
    $statusUpdated = (int) $latestRow['timestamp'];
}

# fetch rows from today only
$queryToday = "
    SELECT timestamp, movement_direction
    FROM observations
    WHERE timestamp / 1000 >= UNIX_TIMESTAMP(CURDATE())
      AND timestamp / 1000 < UNIX_TIMESTAMP(CURDATE() + INTERVAL 1 DAY)
";
$resultToday = $conn->query($queryToday);


$rowsToday = [];
$excursionsToday = 0;
$timeOutsideToday = 0;
$longestTimeOutsideToday = 0;
$shortestTimeOutsideToday = null;

$lastExitTimestamp = null;
$nowMs = round(microtime(true) * 1000);

if ($resultToday && $resultToday->num_rows > 0) {
    $rowsToday = $resultToday->fetch_all(MYSQLI_ASSOC);

    foreach ($rowsToday as $row) {
        $direction = strtoupper(trim($row['movement_direction']));
        $timestamp = (int) $row['timestamp'];

        if ($direction === 'EXIT') {
            $excursionsToday++;
            $lastExitTimestamp = $timestamp;
        }

        if ($direction === 'ENTRY' && $lastExitTimestamp !== null) {
            $duration += ($timestamp - $lastExitTimestamp);

            if ($duration > 0) {
                $timeOutsideToday += $duration;

                # track longest time outside
                if ($duration > $longestTimeOutsideToday) {
                    $longestTimeOutsideToday = $duration;
                }

                # track shortest time outside
                if ($shortestTimeOutsideToday === null || $duration < $shortestTimeOutsideToday) {
                    $shortestTimeOutsideToday = $duration;
                }

            $lastExitTimestamp = null;
            }
        }
    }

    // Still outside at end of day → count until now
    if ($lastExitTimestamp !== null) {
        $timeOutsideToday += ($nowMs - $lastExitTimestamp);
    }
}

$timeOutsideToday = msToHMS($timeOutsideToday);
$longestTimeOutsideToday = msToHMS($longestTimeOutsideToday);
if ($shortestTimeOutsideToday !== null) {
    $shortestTimeOutsideToday = msToHMS($shortestTimeOutsideToday);
} else {
    $shortestTimeOutsideToday = "00:00:00";
}

function msToHMS($ms) {
    $seconds = floor($ms / 1000);
    $hours = floor($seconds / 3600);
    $minutes = floor(($seconds % 3600) / 60);
    $seconds = $seconds % 60;

    return sprintf("%02d:%02d:%02d", $hours, $minutes, $seconds);
}

$conn->close();

header('Content-Type: application/json');
echo json_encode([
    'observations' => $data,
    'excursions' => $excursions,
    'locationStatus' => $locationStatus,
    'statusUpdated' => $statusUpdated,
    'excursionsToday' => $excursionsToday,
    'timeOutsideToday' => $timeOutsideToday,
    'longestTimeOutsideToday' => $longestTimeOutsideToday,
    'shortestTimeOutsideToday' => $shortestTimeOutsideToday
]);
