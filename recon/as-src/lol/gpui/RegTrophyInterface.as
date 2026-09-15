class lol.gpui.RegTrophyInterface extends lol.gpui.StaffInterface
{
   var _alpha;
   var _parent;
   var _xmouse;
   var _ymouse;
   var attachMovie;
   var bagInfo_txt;
   var bag_mc;
   var close_btn;
   var currDDOperation;
   var ddOperation_arr;
   var dispatchEvent;
   var doLater;
   var dragItemMc;
   var equipment;
   var item_mc;
   var master;
   var moneyPan;
   var onEnterFrame;
   var onMouseMove;
   var priceEnabled;
   var regAllCost_txt;
   var regAllTrophy_btn;
   var regCost_txt;
   var regTrophy_arr;
   var regTrophy_btn;
   var slots;
   var trade;
   var trophy_slot;
   var ddFlag = false;
   function RegTrophyInterface()
   {
      super();
      lol.gpui.StaffInterface.ssType = lol.gpui.StaffInterface.SS_REPAIR;
      this.showItemRepairMod = true;
      this.doLater("init");
      this.slots = new Array();
      this.slots.bag = this.bag_mc;
      this.slots.trophy_slot = this.trophy_slot;
      this.bag_mc.id = "bag";
      this.trophy_slot.id = "trophy_slot";
   }
   function tradeClose()
   {
      this.dispatchEvent({type:"closeWindow"});
   }
   function close()
   {
      this.trade.close();
      this.dispatchEvent({type:"closeWindow"});
   }
   function init()
   {
      this.master = lol.core.Master.getInstance();
      this.trade = this.master.gamer.trade;
      this.equipment = this.master.gamer.equipment;
      this.trade.addEventListener("close",this,this.tradeClose);
      this.trade.addEventListener("addItem",this);
      this.trade.addEventListener("removeItem",this);
      this.master.gamer.addEventListener(lol.events.PlayerEvent.UPDATE_INFO,this,this.userInfoUpdate);
      this.userInfoUpdate();
      this.equipment.addEventListener("addItem",this);
      this.equipment.addEventListener("removeItem",this);
      this.close_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.bag_mc.addEventListener("addItem",this,this.bagAddRemoveItem);
      this.bag_mc.addEventListener("removeItem",this,this.bagAddRemoveItem);
      this.trophy_slot.addEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.trophy_slot.addEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.trophy_slot.addEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.trophy_slot.addEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.regTrophy_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.regTrophy);
      this.regAllTrophy_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.regAllTrophy);
      this.bag_mc.alignEnabled = false;
      this.bag_mc.selectAvailable = false;
      this.bag_mc.selectGroupAvailable = false;
      this.bag_mc.showItemRepairMod = false;
      this.bag_mc.handAlign = true;
      this.bag_mc.handSortMask = [0,0,0,0,0,0,1];
      this.bag_mc.bagPan.setSize(185,332);
      this.bag_mc.priceEnabled = true;
      lol.core.SceneShifter.hotKeyManager.addFilter("cancel");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
      this.initObjects();
   }
   function kill()
   {
      this.trade.removeEventListener("close",this,this.tradeClose);
      this.trade.removeEventListener("addItem",this);
      this.trade.removeEventListener("removeItem",this);
      this.master.gamer.removeEventListener(lol.events.PlayerEvent.UPDATE_INFO,this,this.userInfoUpdate);
      this.equipment.removeEventListener("addItem",this);
      this.equipment.removeEventListener("removeItem",this);
      this.close_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.bag_mc.removeEventListener("addItem",this,this.bagAddRemoveItem);
      this.bag_mc.removeEventListener("removeItem",this,this.bagAddRemoveItem);
      this.trophy_slot.removeEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.trophy_slot.removeEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.trophy_slot.removeEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.trophy_slot.removeEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.regTrophy_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.regTrophy);
      this.regAllTrophy_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.regAllTrophy);
      lol.core.SceneShifter.hotKeyManager.removeFilter("cancel");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
   }
   function initObjects()
   {
      this.initBag(this.equipment.bag);
      this.regCostCount();
   }
   function regTrophy()
   {
      var _loc2_ = lol.core.objects.Trophy(this.trophy_slot.item_mc.item);
      if(_loc2_)
      {
         this.trade.addEventListener("regAck",this,this.regAck);
         this.trade.regTrophy(_loc2_);
         this.trophy_slot.item_mc.blockItem();
      }
   }
   function regAck(obj)
   {
      this.trade.removeEventListener("repAck",this,this.regAck);
      this.trophy_slot.item_mc.unblockItem();
      if(obj.param.res == "0")
      {
         this.regTrophyAnimation();
         this.regCost_txt.text = "0";
         this.regTrophy_btn.enabled = false;
      }
   }
   function regAllTrophy()
   {
      var _loc4_ = "Сохранить все\r трофеи?\r<B>Стоимость: " + this.countAllRepairCost() + " А</B>";
      this.openQuery(_loc4_).addEventListener("click",this,this._regAllTrophy);
      this.regTrophy_arr = new Array();
      var _loc2_ = this.bag_mc.sortList;
      for(var _loc3_ in _loc2_)
      {
         _loc2_[_loc3_].blockItem();
         this.regTrophy_arr.push(_loc2_[_loc3_]);
      }
      if(this.trophy_slot.item_mc.item)
      {
         this.trophy_slot.item_mc.blockItem();
         this.regTrophy_arr.push(this.trophy_slot.item_mc);
      }
   }
   function _regAllTrophy(obj)
   {
      obj.target.removeEventListener("click",this,this._regAllTrophy);
      lol.core.SceneShifter.closeWindow("query");
      var _loc3_;
      var _loc2_;
      if(obj.success)
      {
         this.trade.addEventListener("regAck",this,this.regAllAck);
         _loc3_ = 0;
         while(_loc3_ < this.regTrophy_arr.length)
         {
            _loc2_ = this.regTrophy_arr[_loc3_].item;
            this.trade.regTrophy(_loc2_);
            _loc3_ = _loc3_ + 1;
         }
      }
      else
      {
         for(_loc3_ in this.regTrophy_arr)
         {
            this.regTrophy_arr[_loc3_].unblockItem();
         }
      }
   }
   function regAllAck(obj)
   {
      var _loc2_ = lol.gpui.ItemContainer(this.regTrophy_arr.shift());
      if(obj.param.res == "0")
      {
         if(_loc2_ == this.trophy_slot.item_mc)
         {
            _loc2_.unblockItem();
            this.trophy_slot.removeItem(this.trophy_slot.item);
         }
      }
      else
      {
         _loc2_.unblockItem();
      }
      if(this.regTrophy_arr.length == 0)
      {
         this.trade.removeEventListener("repAck",this,this.regAllAck);
      }
   }
   function regTrophyAnimation()
   {
      var n = 1;
      this.trophy_slot.onEnterFrame = function()
      {
         n *= 1.5;
         this._alpha = 100 - n;
         if(this._alpha < 0)
         {
            delete this.onEnterFrame;
            this._parent.removeItem({slot:this,item:this.item_mc.item});
            this._alpha = 100;
         }
      };
   }
   function bagAddRemoveItem(obj)
   {
      this.doLater("bagInfo");
      this.regCostCount();
   }
   function bagInfo()
   {
      var _loc3_ = new TextFormat();
      _loc3_.bold = true;
      var _loc2_ = this.bag_mc.sortList.length;
      _loc2_ = _loc2_ != undefined ? _loc2_ : 0;
      this.bagInfo_txt.text = _loc2_;
      this.bagInfo_txt.setTextFormat(_loc3_);
   }
   function regCostCount()
   {
      var _loc3_ = this.trophy_slot.item_mc.item;
      var _loc2_;
      if(_loc3_)
      {
         _loc2_ = _loc3_.getProp("cost");
         _loc2_ = _loc2_ != 0 ? _loc2_ : 1;
         this.regCost_txt.text = _loc2_;
         this.regTrophy_btn.enabled = true;
      }
      else
      {
         this.regCost_txt.text = "0";
         this.regTrophy_btn.enabled = false;
      }
      if(this.countAllRepairCost())
      {
         this.regAllCost_txt.text = String(this.countAllRepairCost());
         this.regAllTrophy_btn.enabled = true;
      }
      else
      {
         this.regAllCost_txt.text = "0";
         this.regAllTrophy_btn.enabled = false;
      }
   }
   function countAllRepairCost()
   {
      var _loc5_ = 0;
      var _loc4_ = this.bag_mc.sortList;
      var _loc2_ = 0;
      var _loc3_;
      var _loc6_;
      while(_loc2_ < _loc4_.length)
      {
         _loc3_ = _loc4_[_loc2_].item;
         _loc6_ = _loc3_.getProp("cost");
         if(_loc6_)
         {
            _loc5_ += _loc6_;
         }
         _loc2_ = _loc2_ + 1;
      }
      if(this.trophy_slot.item_mc.item)
      {
         _loc6_ = this.trophy_slot.item_mc.item.getProp("cost");
         if(_loc6_)
         {
            _loc5_ += _loc6_;
         }
      }
      return _loc5_;
   }
   function startDragNDrop(obj)
   {
      if(!this.ddOperation_arr)
      {
         this.ddOperation_arr = new Array();
      }
      var _loc2_ = obj.item_mc;
      var _loc3_ = obj.target;
      _loc2_.blockItem();
      this.ddFlag = true;
      this.createDragItemMc(_loc2_.item);
      this.currDDOperation = new lol.gpui.DDOperation();
      this.currDDOperation.setFrom(_loc2_.__item,_loc3_,_loc2_);
   }
   function createDragItemMc(_item)
   {
      if(this.typeOfList == "icon")
      {
         this.dragItemMc = lol.gpui.ItemContainer(this.attachMovie("itemCont","dd",10));
         this.dragItemMc.attachIconEnabled = true;
      }
      else if(this.typeOfList == "list")
      {
         this.dragItemMc = lol.gpui.ItemContainer(this.attachMovie("listItemCont","dd",10));
         this.dragItemMc.attachIconEnabled = false;
      }
      this.dragItemMc.priceEnabled = this.priceEnabled;
      this.dragItemMc.showItemRepairMod = this.showItemRepairMod;
      this.dragItemMc.cost_mod = this.cost_mod;
      this.dragItemMc.item = _item;
      this.dragItemMc.attachIcon(_item);
      this.draggingItem();
      this.onMouseMove = this.draggingItem;
   }
   function doubleClick(obj)
   {
      var _loc2_ = obj.item_mc;
      if(obj.target == this.bag_mc)
      {
         if(this.trophy_slot.item_mc.item)
         {
            this.bag_mc.addItem(this.trophy_slot.item_mc.item);
         }
         this.trophy_slot.addItem(_loc2_.item);
         this.bag_mc.removeItem(_loc2_.item);
      }
      else
      {
         this.bag_mc.addItem(this.trophy_slot.item_mc.item);
         this.trophy_slot.removeItem(this.trophy_slot.item_mc.item);
      }
   }
   function mouseUpOnItem(obj)
   {
      var _loc2_;
      if(this.ddFlag)
      {
         _loc2_ = obj.item_mc;
         this.currDDOperation.setTo(_loc2_.item,obj.target,_loc2_);
      }
   }
   function dropItem(obj)
   {
      var _loc3_;
      if(this.ddFlag)
      {
         _loc3_ = obj.target;
         this.currDDOperation.setTo(0,obj.target);
      }
   }
   function onMouseUp()
   {
      if(this.ddFlag)
      {
         this.ddFlag = false;
         this.dragItemMc.kill();
         this.dragItemMc.removeMovieClip();
         if(this.currDDOperation.fromSlot == this.bag_mc && this.currDDOperation.toSlot == this.trophy_slot)
         {
            if(this.trophy_slot.item_mc.item)
            {
               this.bag_mc.addItem(this.trophy_slot.item_mc.item);
            }
            this.trophy_slot.addItem(this.currDDOperation.fromItem);
            this.bag_mc.removeItem(this.currDDOperation.fromItem);
         }
         else if(this.currDDOperation.fromSlot == this.trophy_slot && this.currDDOperation.toSlot == this.bag_mc)
         {
            this.bag_mc.addItem(this.currDDOperation.fromItem);
            this.trophy_slot.removeItem(this.currDDOperation.fromItem);
         }
         else
         {
            this.currDDOperation.failedOperation();
            delete this.currDDOperation;
         }
      }
      delete this.onMouseMove;
   }
   function draggingItem()
   {
      this.dragItemMc._x = Math.round(this._xmouse - this.dragItemMc._width / 2);
      this.dragItemMc._y = Math.round(this._ymouse - this.dragItemMc._height / 2);
   }
   function userInfoUpdate(obj)
   {
      this.showMoney(this.master.gamer.attributes.afro);
   }
   function showMoney(afro)
   {
      this.moneyPan.value = afro;
   }
   function openAlert(str)
   {
      var _loc1_ = lol.gpui.dialogue.GPUIAlert(lol.core.SceneShifter.openNewWindow("alert").content);
      _loc1_.label = str;
      return _loc1_;
   }
   function openQuery(str)
   {
      var _loc1_ = lol.gpui.dialogue.GPUIDialogue(lol.core.SceneShifter.openNewWindow("query").content);
      _loc1_.label = str;
      return _loc1_;
   }
}
