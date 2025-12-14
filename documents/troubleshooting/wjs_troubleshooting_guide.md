# WJS Troubleshooting Guide

This document provides standardized troubleshooting procedures for **Wireless Jackpot Signs (WJS)**, covering **Admart** and **Carmanah** models, as well as **transceiver and network-related issues**.

Use this guide to quickly identify symptoms and apply the correct corrective actions in the field.

---

## 1. Admart — Sign Not Receiving Power

### Failure Indicators
- Display is blank or non-responsive  
- Sign appears powered down  
- Random or continuous restarts  
- Visible damage, looseness, or instability in power cabling  

> Refer to the example image showing an Admart sign with no power.

### Corrective Actions
1. Inspect all power cables and connectors for physical damage or loose connections.
2. Replace the power adapter.
3. Replace the power supply cable.
4. Power-cycle the sign and confirm normal startup.

---

## 2. Admart — Sign Flashing Decimal Points

### Failure Indicators
- Decimal points flashing or cycling continuously  
- Terminal unable to establish communication with the sign  
- Transceiver not powered or malfunctioning  
- Channel mismatch between the sign and transceiver  

> Refer to the example image showing flashing decimal points on an Admart sign.

### Corrective Actions
1. Confirm the transceiver is receiving power.
2. Replace the transceiver if no power or erratic behavior is observed.
3. Verify that the sign is properly installed and configured in the OLG terminal.
4. Ensure the transceiver is connected to the correct communication port.
5. Inspect the DIP switch channel settings on both the sign and the transceiver.
6. Confirm both devices are set to the **same channel**.
7. Retest communication after adjustments.

---

## 3. Carmanah — Sign Not Receiving Power

### Failure Indicators
- Display is blank or non-responsive  
- Sign appears powered down  
- Unexpected restart cycles  
- Damaged or loose power cabling  

> Refer to the example image showing a Carmanah sign with no power.

### Corrective Actions
1. Inspect all power cables and connectors for damage or looseness.
2. Verify the power adapter output is stable and correct.
3. Replace the power adapter with a verified working unit.
4. Replace the DC power cable if defects are found.
5. Restart the sign and confirm normal operation.

---

## 4. Carmanah — Sign Flashing Decimal Points

### Failure Indicators
- Decimal points flashing or cycling  
- Sign not receiving data from the network  
- Transceiver not powered  
- Ethernet cable disconnected or faulty  
- Incorrect router port assignment  

> Refer to the example image showing flashing decimal points on a Carmanah sign.

### Corrective Actions
1. Verify the transceiver is powered on.
2. Ensure the Ethernet cable is properly connected.
3. Replace the transceiver if no power or unstable behavior is observed.
4. Confirm the Ethernet cable is connected to **Port 2 (Carmanah port)** on the Cisco router.
5. If the issue persists, reboot the router:
   - Press the black reset button on the back of the Cisco router.
   - Wait **30 seconds**, then press again to power the router back on.
6. Inform the retailer that the OLG terminal will be temporarily offline.
7. Retest communication after the router restarts.

---

## 5. Carmanah — Sign Has Moving Decimal Points

### Failure Indicators
- Decimal points moving or shifting across the display  

This condition typically indicates:
- Unstable network connectivity  
- Transceiver communication degradation  
- Ethernet cable or router-related fault  

> Refer to the example image showing moving decimal points on a Carmanah sign.

### Corrective Actions
1. Replace the transceiver power supply.
2. Replace the transceiver if unstable operation persists.
3. Replace the Ethernet cable and retest connectivity.
4. Reboot the router:
   - Locate the black reset button on the Cisco router.
   - Press the button **twice** to restart the router.
5. Notify the retailer that the OLG terminal will be offline (may take up to **15 minutes**).
6. Restart the OLG terminal after the router is fully back online.
7. Test using a known working Carmanah sign.
8. If the issue persists:
   - Contact the office to report a network connectivity issue.
   - Confirm authorization before replacing the Carmanah sign with an Admart sign.

---

## 6. Transceiver — Green LED / No Network Connection

### Failure Indicators
- Transceiver shows a **steady green LED**
- No network communication detected  

This condition indicates that the transceiver is powered but **not receiving a valid network signal**.

> Refer to the example image showing a transceiver with a steady green LED.

### Corrective Actions
1. Replace the transceiver.
2. Replace the Ethernet/network cable.
3. Replace the transceiver power supply.
4. Restart the router if all previous steps fail.

---

## 7. Router — Network Reset Procedure

### Failure Indicators
- Multiple signs not communicating  
- Repeated communication failures after transceiver replacement  

> Refer to the example image showing the Cisco router reset button.

### Corrective Actions
1. Inform the retailer that the OLG terminal will be temporarily offline.
2. Locate the black reset button on the back of the Cisco router.
3. Press the button **once** to power off the router.
4. Wait **30 seconds**.
5. Press the button again to power the router back on.
6. Allow up to **15 minutes** for full network recovery.
7. Restart the OLG terminal after the router is fully online.
8. Verify sign communication status.

---

## Escalation Guidelines

If all troubleshooting steps have been completed and the issue persists:

- The problem may be related to:
  - Backend configuration issues
  - Network security restrictions
  - Infrastructure outages

Escalate the issue through the appropriate internal support channels and **do not proceed with further hardware replacement without authorization**.

---

## Technician Notes

- Always document:
  - Symptoms observed
  - Actions performed
  - Components replaced
- Capture photos when required and upload them according to internal procedures.
