"""Actual demo control moved into its information dialog; safety still syncs."""
from playwright.sync_api import expect
def toggle_vehicle(page):
    page.get_by_role('button',name='Demo araç durumu hakkında bilgi',exact=True).click()
    page.get_by_title('Sürüş ve Park modları arasında geçiş').click()
    page.keyboard.press('Escape')
def vehicle_status(page):
    return page.locator('[data-vehicle-status]')
