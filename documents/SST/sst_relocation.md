# SST Relocation Procedure

## Table of Contents
1. Pre-Visit Preparation
2. On-Site Procedure
    - Arrival and Retailer Engagement
    - Document the SST Status
    - Backup Accounting Database
    - Moving to the New Location
    - Reactivating SST
    - Final Steps
    - Call Completion

---

## Pre-Visit Preparation
Technicians will receive the retail location details, site information, and contact information, along with instructions specifying the type of relocation required. This could involve switching the site from cable to LTE or running new network cables to accommodate the SST’s new location.

**Important Notes:**
- Refer to the "SST Staging" document to identify an LTE vs. Cable site.
- **LTE Conversion:** If the setup involves converting from a cabled site to LTE, ensure you have the correct router for the SST site (request from warehouse associates).
- **Cabled Site:** If existing network cables are available, safely redirect and test the cables using a fluke tester to verify functionality.
- **Tools:** Review the site survey before the visit to ensure you have necessary tools such as dollies, air sleds, or a track-o.

---

## On-Site Procedure

### 1. Arrival and Retailer Engagement
- Upon arrival, introduce yourself professionally and inform the retailer of the purpose of your visit.
- Request the **SST keys** to perform the service, ensuring they are returned once the task is completed.

### 2. Document the SST Status
- Take a photo of the **SST in retailer mode** to document its current status.
- Use the key to **unlock the SST door** and disarm the alarm by pressing the button located on the left of the CPU.

### 3. Backup Accounting Database
1. **Login:** On the 7” screen, use Login **4567** and Password **456789**.
2. **Print Report:** Navigate to `REPORTS > INVENTORY`. Tap the printer icon on the top right and select "Full Page Print".
3. **Documentation:** Take a photo of the inventory report.
4. **Debug Mode:** Enter debug mode by inserting the USB drive into one of the debug slots on the CPU.
5. **Power Down:** Once the backup is complete, power down the SST before proceeding with the move.

### 4. Moving to the New Location
*Refer to the "SST Handling" document for safe handling practices,.*

- **If Switching to LTE:** Stage the SST for LTE setup, which includes adding raceway to the back of the unit and securing network and power cables with two 45-degree cut pieces at the top.
- **If Cabled Site:** Cables may have to be rerun and tested depending on the distance; document the number of feet of cabling used.
- **Move:** Move the SST to the new requested location.

### 5. Reactivating SST
1. After relocating and connecting network cables, power on the SST in **debug mode**.
2. **Restore Data:** Navigate to `MAIN MENU > EXTENDED DIAGS > PERIPHERALS > ACCOUNTING NVRAM > RESTORE ACCOUNTING NVRAM`.
3. Once the restore is successful, turn off the SST and remove the USB.

### 6. Final Steps
- **Verify Function:** Print an inventory report and verify that the SST is functioning as expected.
- **Test Pin Pad:** Scan an ID card and prompt for a purchase transaction to test the pin pad. Take a photo of the transaction for proof.
- **Call Clear Slip:** A call clear slip is required upon completion; failure to submit this form will result in the call being marked as incomplete.

### 7. Call Completion
Take a final picture of the SST to confirm its status and handover.

**Required Documentation (Photos and Notes):**
Ensure you have the following before completing the call:
- Call Clear Slip
- Site condition
- Inventory reports (before and after)
- Elite terminal RDL router
- LTE router S/N (if applicable)
- Pin pad tested
- SST in confirmed working condition
- SST in new location
