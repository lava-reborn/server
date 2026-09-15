class lol.gpui.OutfitInterface extends lol.gpui.GPUIObject
{
   var armor_mc;
   var belt_mc;
   var boots_mc;
   var cam_mc;
   var dispatchEvent;
   var dragZone;
   var head_mc;
   var legs_mc;
   var level_txt;
   var name_txt;
   var playerBody_mc;
   var prim_mc;
   var sec_mc;
   var slots;
   var dragEnabled = true;
   function OutfitInterface()
   {
      super();
      this.slots = new Array();
      this.slots.primary = this.prim_mc;
      this.slots.secondary = this.sec_mc;
      this.slots.head = this.head_mc;
      this.slots.armor = this.armor_mc;
      this.slots.camouflage = this.cam_mc;
      this.slots.legs = this.legs_mc;
      this.slots.boots = this.boots_mc;
      this.slots.belt = this.belt_mc;
      this.doLater("init");
   }
   function init()
   {
      this.setSlot(this.prim_mc,"hand","primary");
      this.setSlot(this.sec_mc,"hand","secondary");
      this.setSlot(this.head_mc,"wear","head");
      this.setSlot(this.armor_mc,"wear","armor");
      this.setSlot(this.cam_mc,"wear","camouflage");
      this.setSlot(this.legs_mc,"wear","legs");
      this.setSlot(this.boots_mc,"wear","boots");
      this.setSlot(this.belt_mc,"wear","belt");
      this.setSlot(this.dragZone,"dragZone","dragZone");
      this.prim_mc.addEventListener(lol.gpui.ItemContainer.RELOAD,this,this.onReload);
      this.sec_mc.addEventListener(lol.gpui.ItemContainer.RELOAD,this,this.onReload);
   }
   function kill()
   {
      this.killSlot(this.prim_mc);
      this.killSlot(this.sec_mc);
      this.killSlot(this.head_mc);
      this.killSlot(this.armor_mc);
      this.killSlot(this.cam_mc);
      this.killSlot(this.legs_mc);
      this.killSlot(this.boots_mc);
      this.killSlot(this.belt_mc);
      this.killSlot(this.dragZone);
      this.prim_mc.removeEventListener(lol.gpui.ItemContainer.RELOAD,this,this.onReload);
      this.sec_mc.removeEventListener(lol.gpui.ItemContainer.RELOAD,this,this.onReload);
   }
   function setPlayer(player)
   {
      var _loc2_ = player.playerInfo.resID;
      var _loc4_ = lol.services.SSEmulator.getAvatarURL(_loc2_,1);
      var _loc5_ = lol.display.DisplaySprite.create(this.playerBody_mc,"av",0);
      _loc5_.display("big_avatar" + _loc2_,_loc4_);
      this.name_txt.text = !player.playerInfo.name ? "" : player.playerInfo.name;
      this.level_txt.text = "Уровень " + player.attributes.level;
   }
   function setSlot(slot_mc, type, name)
   {
      slot_mc.addEventListener(lol.gpui.ItemContainer.SELECT,this,this.select);
      slot_mc.addEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      slot_mc.addEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      slot_mc.addEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      slot_mc.addEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      slot_mc.id = name;
      slot_mc.type = type;
      slot_mc.name = name;
      slot_mc.useHandCursor = false;
   }
   function killSlot(slot_mc)
   {
      slot_mc.removeEventListener(lol.gpui.ItemContainer.SELECT,this,this.select);
      slot_mc.removeEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      slot_mc.removeEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      slot_mc.removeEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      slot_mc.removeEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
   }
   function startDragNDrop(obj)
   {
      var _loc2_ = new Array();
      _loc2_.push(obj.item_mc);
      this.dispatchEvent({type:lol.gpui.ItemContainer.START_DRAG_N_DROP,item_mc:obj.item_mc,item_arr:_loc2_,target:obj.target});
   }
   function select(obj)
   {
      this.dispatchEvent({type:lol.gpui.ItemContainer.SELECT,item_mc:obj.item_mc,target:obj.target});
   }
   function doubleClick(obj)
   {
      this.dispatchEvent({type:lol.gpui.ItemContainer.DOUBLE_CLICK,item_mc:obj.item_mc,target:obj.target});
   }
   function mouseUpOnItem(obj)
   {
      this.dispatchEvent({type:lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,item_mc:obj.item_mc,target:obj.target});
   }
   function dropItem(obj)
   {
      this.dispatchEvent({type:lol.gpui.ItemContainer.DROP,item_mc:obj.item_mc,target:obj.target});
   }
   function onReload(obj)
   {
      this.dispatchEvent(obj);
   }
   function addItem(obj)
   {
      var _loc4_ = obj.slot;
      var _loc5_ = obj.item;
      var _loc6_ = obj.i;
      var _loc2_ = this.slots[_loc4_.id];
      _loc2_.addItem(_loc5_,_loc6_);
   }
   function removeItem(obj)
   {
      var _loc3_ = obj.slot;
      var _loc4_ = obj.item;
      var _loc2_ = this.slots[_loc3_.id];
      _loc2_.removeItem(_loc4_);
   }
   function selectSlot(id)
   {
      var _loc2_ = this[id + "_mc_border"];
      _loc2_.gotoAndStop(2);
   }
   function clearSelect()
   {
      for(var _loc2_ in this.slots)
      {
         this[_loc2_ + "_mc_border"].gotoAndStop(1);
      }
   }
   function getSlot(str)
   {
      var _loc2_;
      switch(str)
      {
         case 0:
            _loc2_ = this.head_mc;
            break;
         case 1:
            _loc2_ = this.cam_mc;
            break;
         case 2:
            _loc2_ = this.armor_mc;
            break;
         case 4:
            _loc2_ = this.legs_mc;
            break;
         case 5:
            _loc2_ = this.boots_mc;
            break;
         default:
            _loc2_;
      }
      return _loc2_;
   }
}
