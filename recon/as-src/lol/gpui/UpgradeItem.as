class lol.gpui.UpgradeItem extends lol.gpui.GPUIObject
{
   var _slotPan;
   var afterItem;
   var beforeItem;
   var cost_txt;
   var dispatchEvent;
   var upgrade_btn;
   function UpgradeItem()
   {
      super();
   }
   function init(_beforeItem, _afterItem)
   {
      this.beforeItem = _beforeItem;
      this.afterItem = _afterItem;
      var _loc3_ = new TextFormat();
      _loc3_.bold = true;
      var _loc2_ = Number(_afterItem.getProp("_cost"));
      this.cost_txt.text = "G " + String(_loc2_ * 0.01);
      this._slotPan.dragEnabled = false;
      this.doLater("initBtn");
   }
   function kill()
   {
      this._slotPan.removeItem();
      this.upgrade_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.upgrade);
   }
   function initBtn()
   {
      this._slotPan.addItem(this.afterItem);
      this.upgrade_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.upgrade);
   }
   function upgrade()
   {
      this.dispatchEvent({type:"upgrade",num:1,beforeItem:this.beforeItem,afterItem:this.afterItem});
   }
}
