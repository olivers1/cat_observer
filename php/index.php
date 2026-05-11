<!DOCTYPE html>
<html>
<head>
<style>
    td, th {
        border: 0.5px solid black;
        padding: 6px;
        text-align: center;
        font-family: helvetica;
        font-size: 14px;
    }

    /* Container for ASCII cat + title */
    .header-container {
        display: flex;
        align-items: center; /* vertically center title with cat */
        justify-content: left; /* align left */
    }

    /* ASCII cat styling */
    .ascii-cat {
        font-family: monospace;
        margin-right: 20px; /* space between cat and title */
        line-height: 1; /* tight spacing for ASCII art */
    }

    /* Title styling */
    h1 {
        font-family: helvetica;
        margin: 0; /* remove default margin */
    }

    /* Date/time display styling */
    #current-datetime, #excursions-count, #status-location, #status-updated, #excursions-today, #time-outside-today {
        font-family: helvetica;
        font-size: 14px;
        margin-left: 5px;
        margin-bottom: 2px;
    }

</style>
</head>

<body>

<div class="header-container">
    <pre class="ascii-cat">
 /\_/\  
( o.o ) 
 > ^ <
    </pre>
    <h1>Cat ObServer</h1>
</div>

<div id="status-location"></div>
<div id="status-updated"></div>
<div id="excursions-today"></div>
<div id="time-outside-today"></div>
<br>
<div id="excursions-count"></div>
<br>

<!-- Current date/time display just above the table -->
<div id="current-datetime">
    Time now: <span id="current-time"></span>
</div>


<table>
    <thead>
        <tr>
            <th>Timestamp (ms)</th>
            <th>Date & Time</th>
            <th>Movement Direction</th>
        </tr>
    </thead>
    <tbody id="table-body">
        <!-- Data will be inserted here -->
    </tbody>
</table>

<script>
async function loadData() {
    try {
        const response = await fetch('fetch_observations.php');
        const data = await response.json();

        const observations = data.observations;
        const excursions = data.excursions;
        const locationStatus = data.locationStatus;
        const statusUpdated = data.statusUpdated;
        const formattedStatusUpdated = formatTimestamp(statusUpdated, {
            fallback: 'Unknown'
        });
        const excursionsToday = data.excursionsToday;
        const timeOutsideToday = data.timeOutsideToday;
        const longestTimeOutsideToday = data.longestTimeOutsideToday;
        const shortestTimeOutsideToday = data.shortestTimeOutsideToday;

        // Display excursions count
        document.getElementById('excursions-count').textContent = `Total excursions: ${excursions}`;
        // Display location status
        document.getElementById('status-location').textContent = `Status: ${locationStatus}`;
        // Display status updated time
        document.getElementById('status-updated').textContent = `Updated: ${formattedStatusUpdated}`;
        // Display today excursions
        document.getElementById('excursions-today').textContent = `Excursions today: ${excursionsToday}`;
        // Display total time outside today
        document.getElementById('time-outside-today').textContent = `Time outside today: ${timeOutsideToday}`;


        const tbody = document.getElementById('table-body');
        tbody.innerHTML = '';

        observations.forEach(row => {
            const formattedDate = formatTimestamp(row.timestamp);

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${row.timestamp}</td>
                <td>${formattedDate}</td>
                <td>${row.movement_direction}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error('Failed to load data', err);
    }
}

function formatTimestamp(timestamp, options = {}) {
    const {
        formatter = (date) => date.toLocaleString(),
        fallback = ''
    } = options;

    const ts = Number(timestamp);
    if (isNaN(ts)) {
        console.warn('Invalid timestamp:', timestamp);
        return fallback;
    }

    return formatter(new Date(ts));
}

// Update current date and time every second
function updateDateTime() {
    const now = new Date();
    document.getElementById('current-datetime').textContent = now.toLocaleString();
}

updateDateTime();
setInterval(updateDateTime, 1000);

loadData();
setInterval(loadData, 5000);
</script>

</body>
</html>
