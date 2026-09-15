class lol.gpui.UpgradeAmmoItem extends lol.gpui.GPUIObject
{
   var afterItem;
   var beforeItem;
   var cost_txt;
   var dispatchEvent;
   var maxSize;
   var minus_btn;
   var mod_mc;
   var numCur;
   var num_txt;
   var plus_btn;
   var prop1_txt;
   var prop2_txt;
   var prop3_txt;
   var prop4_txt;
   var prop0_txt;
   var title_txt;
   var upgrade_btn;
   function UpgradeAmmoItem()
   {
      super();
   }
   function UpgradeItem()
   {
   }
   function init(_beforeItem, _afterItem)
   {
      this.beforeItem = _beforeItem;
      this.afterItem = _afterItem;
      var _loc3_ = new TextFormat();
      _loc3_.bold = true;
      this.title_txt.text = this.afterItem.getProp("name");
      this.title_txt.setTextFormat(_loc3_);
      this.prop0_txt.text = this.afterItem.getProp("range_mod");
      this.prop1_txt.text = this.afterItem.getProp("acc_mod");
      this.prop2_txt.text = this.afterItem.getProp("dam_mod");
      this.prop3_txt.text = this.afterItem.getProp("st_mod");
      this.prop4_txt.text = this.afterItem.getProp("piercing");
      this.cost_txt.text = "G " + String(Number(this.afterItem.getProp("_cost")) * 0.01);
      this.maxSize = this.beforeItem.getProp("size");
      this.num_txt.text = String(this.maxSize);
      this.num_txt.restrict = "0-9";
      this.doLater("initBtn");
      var _loc2_ = this.afterItem.getProp("mod_type");
      var _loc4_ = lol.core.objects.Ammo.MOD_ARR[_loc2_];
      this.mod_mc.gotoAndStop(_loc2_);
      this.num_txt.onChanged = mx.utils.Delegate.create(this,this.textChanged);
   }
   function textChanged()
   {
      if(this.num_txt.text < 1)
      {
         this.num_txt.text = this.numCur;
      }
      else if(this.num_txt.text > this.maxSize)
      {
         this.num_txt.text = this.numCur;
      }
      else
      {
         this.numCur = this.num_txt.text;
      }
   }
   function initBtn()
   {
      this.upgrade_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.upgrade);
      this.plus_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.plus);
      this.minus_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.minus);
   }
   function upgrade()
   {
      this.dispatchEvent({type:"upgrade",num:this.num_txt.text,beforeItem:this.beforeItem,afterItem:this.afterItem});
   }
   function plus()
   {
      if(this.num_txt.text < this.maxSize)
      {
         this.num_txt.text = String(Number(this.num_txt.text) + 1);
      }
   }
   function minus()
   {
      if(this.num_txt.text > 1)
      {
         this.num_txt.text = String(Number(this.num_txt.text) - 1);
      }
   }
}
