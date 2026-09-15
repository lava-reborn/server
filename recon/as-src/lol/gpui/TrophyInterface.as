class lol.gpui.TrophyInterface extends lol.gpui.StaffInterface
{
   var _xmouse;
   var _ymouse;
   var addSlot_btn;
   var attachMovie;
   var cancelSearch_btn;
   var currDDOperation;
   var currSelect;
   var ddOperation_arr;
   var delete_btn;
   var doLater;
   var dragItemMc;
   var equipment;
   var gamer;
   var master;
   var onMouseMove;
   var priceEnabled;
   var publicListPan;
   var publicSlotNum;
   var publicTrophyList_arr;
   var publicTrophy_arr;
   var search_txt;
   var sortByTime_btn;
   var sortByType_btn;
   var sortByVName_btn;
   var sortByVlvl_btn;
   var sortTrophyList_arr;
   var tf;
   var trophyInfo_txt;
   var trophyListPan;
   var trophyManager;
   var trophy_arr;
   var n = 0;
   var m = 0;
   var ddFlag = false;
   function TrophyInterface()
   {
      super();
      this.master = lol.core.Master.getInstance();
      this.gamer = this.master.gamer;
      this.equipment = this.gamer.equipment;
      this.gamer.trophyManager = new lol.core.player.TrophyManager();
      this.trophyManager = this.gamer.trophyManager;
      this.tf = new TextFormat();
      this.tf.bold = true;
      this.cancelSearch_btn._visible = false;
      this.doLater("init");
   }
   function init()
   {
      this.trophyManager.addEventListener(lol.core.player.TrophyManager.PUBLIC_SLOT_NUM,this,this.setPublicSlotNum);
      this.trophyManager.addEventListener(lol.core.player.TrophyManager.TROPHY_LIST,this,this.setTrophyList);
      this.trophyManager.addEventListener(lol.core.player.TrophyManager.DELETE_TROPHY,this,this.deleteTrophyAck);
      this.equipment.addEventListener("requestPublicTrophy",this,this.setPublicTrophyList);
      this.sortByType_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortBy);
      this.sortByVlvl_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortBy);
      this.sortByVName_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortBy);
      this.sortByTime_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortBy);
      this.sortByType_btn.data = "type";
      this.sortByVlvl_btn.data = "v_lvl";
      this.sortByVName_btn.data = "v_name";
      this.sortByTime_btn.data = "time";
      this.sortByType_btn.hintTitle_str = "Сортировать трофеи по типу";
      this.sortByVlvl_btn.hintTitle_str = "Сортировать трофеи по уровню жертвы";
      this.sortByVName_btn.hintTitle_str = "Сортировать трофеи по имени жертвы";
      this.sortByTime_btn.hintTitle_str = "Сортировать трофеи по дате";
      this.delete_btn.addEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this,this.deleteTrophy);
      this.delete_btn.hintTitle_str = "Удалить трофей";
      this.search_txt.onChanged = mx.utils.Delegate.create(this,this.search);
      this.addSlot_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.addSlot);
      this.cancelSearch_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.cancelSearch);
      this.cancelSearch_btn.hintTitle_str = "Сбросить поиск";
      lol.core.SceneShifter.hotKeyManager.addFilter("trophy");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.ESC,this,this.pressEscKey);
      this.trophyManager.createSession();
   }
   function kill()
   {
      this.trophyManager.closeSession();
      this.trophyManager.removeEventListener(lol.core.player.TrophyManager.PUBLIC_SLOT_NUM,this,this.setPublicSlotNum);
      this.trophyManager.removeEventListener(lol.core.player.TrophyManager.TROPHY_LIST,this,this.setTrophyList);
      this.trophyManager.removeEventListener(lol.core.player.TrophyManager.DELETE_TROPHY,this,this.deleteTrophyAck);
      this.equipment.removeEventListener("requestPublicTrophy",this,this.setPublicTrophyList);
      this.sortByType_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortBy);
      this.sortByVlvl_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortBy);
      this.sortByVName_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortBy);
      this.sortByTime_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortBy);
      this.addSlot_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.addSlot);
      this.cancelSearch_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.cancelSearch);
      this.delete_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.deleteTrophy);
      lol.core.SceneShifter.hotKeyManager.removeFilter("trophy");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.ESC,this,this.pressEscKey);
   }
   function cancel()
   {
      lol.core.SceneShifter._sl.closeWinBtn_func();
   }
   function setPublicSlotNum(obj)
   {
      this.publicSlotNum = obj.num;
   }
   function setTrophyList(obj)
   {
      this.trophyListPan.setSize(520,335);
      this.trophyListPan.fillContent();
      this.trophy_arr = this.trophyManager.trophy_arr;
      this.sortTrophyList_arr = new Array();
      this.n = 0;
      this.m = 0;
      var _loc2_;
      var _loc6_;
      var _loc3_;
      var _loc9_;
      var _loc8_;
      var _loc5_;
      var _loc7_;
      var _loc4_;
      for(var _loc12_ in this.trophy_arr)
      {
         _loc2_ = this.trophy_arr[_loc12_];
         if(_loc2_)
         {
            _loc6_ = this.addTrophy(_loc2_);
         }
         _loc3_ = _loc2_.getProp("name");
         _loc9_ = _loc2_.getProp("v_name");
         _loc8_ = _loc2_.getProp("v_lvl");
         _loc5_ = _loc2_.getProp("v_clan");
         _loc7_ = _loc2_.getProp("time");
         _loc4_ = _loc3_ + _loc8_ + _loc9_ + _loc5_;
         this.sortTrophyList_arr.push({type:_loc3_,v_name:_loc9_,v_lvl:_loc8_,time:_loc7_,trophy_mc:_loc6_,search:_loc4_});
      }
      this.trophyListPan.chekSize();
      this.unselect();
   }
   function setPublicTrophyList(obj)
   {
      this.publicListPan.setSize(180,253);
      this.publicTrophy_arr = this.equipment.publicTrophy_arr;
      var _loc5_ = this.publicListPan.fillContent();
      this.publicTrophyList_arr = new Array();
      var _loc8_ = 0;
      var _loc3_ = 0;
      var _loc4_;
      var _loc2_;
      while(_loc3_ < this.publicTrophy_arr.length)
      {
         _loc4_ = this.publicTrophy_arr[_loc3_];
         _loc2_ = lol.gpui.SlotPan(_loc5_.attachMovie("trophySlotPan","trophySlotPan" + _loc3_,_loc5_.getNextHighestDepth(),{_x:0,_y:_loc3_ * 85}));
         if(_loc4_)
         {
            _loc2_.addItem(_loc4_);
            _loc8_ = _loc8_ + 1;
         }
         _loc2_.data = _loc3_;
         _loc2_.addEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
         _loc2_.addEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
         _loc2_.addEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
         this.publicTrophyList_arr.push(_loc2_);
         _loc3_ = _loc3_ + 1;
      }
      this.trophyInfo_txt.text = "ЗАНЯТО МЕСТ " + _loc8_ + " ИЗ " + this.publicTrophy_arr.length;
      this.trophyInfo_txt.setTextFormat(this.tf);
      this.publicListPan.chekSize();
      this.unselect();
   }
   function addTrophy(trophyItem)
   {
      var _loc3_ = this.trophyListPan.content;
      var _loc2_ = lol.gpui.ItemContainer(_loc3_.attachMovie("itemCont","itemCont_" + this.n + "_" + this.m,_loc3_.getNextHighestDepth(),{_x:this.m * 170,_y:this.n * 85}));
      _loc2_.item = trophyItem;
      _loc2_.attachIcon(trophyItem);
      _loc2_.addEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      _loc2_.addEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      _loc2_.addEventListener(lol.gpui.ItemContainer.SELECT,this,this.selectTrophy);
      if(this.m < 2)
      {
         this.m = this.m + 1;
      }
      else
      {
         this.m = 0;
         this.n = this.n + 1;
      }
      return _loc2_;
   }
   function addSlot()
   {
      var _loc2_ = lol.gpui.dialogue.GPUIDialogue(lol.core.SceneShifter.openNewWindow("query").content);
      _loc2_.label = "Купить новое место под демонстрируемый трофей?";
      _loc2_.addEventListener("click",this,this._addSlot);
   }
   function _addSlot(obj)
   {
      obj.target.removeEventListener("click",this,this._addSlot);
      lol.core.SceneShifter.closeWindow("query");
      if(obj.success)
      {
         this.trophyManager.addSlot();
         this.trophyManager.addEventListener(lol.core.player.TrophyManager.ADD_SLOT,this,this.addSlotAck);
      }
   }
   function addSlotAck(obj)
   {
      this.trophyManager.removeEventListener(lol.core.player.TrophyManager.ADD_SLOT,this,this.addSlotAck);
      var _loc2_;
      if(!obj.success)
      {
         _loc2_ = lol.gpui.dialogue.GPUIAlert(lol.core.SceneShifter.openNewWindow("alert").content);
         _loc2_.label = "У вас недостаточно денег";
      }
   }
   function startDragNDrop(obj)
   {
      if(!this.ddOperation_arr)
      {
         this.ddOperation_arr = new Array();
      }
      this.ddFlag = true;
      var _loc4_ = obj.target.item;
      var _loc2_;
      var _loc5_;
      if(obj.target.item_mc)
      {
         _loc2_ = obj.target.item_mc;
         _loc5_ = obj.target;
      }
      else
      {
         _loc2_ = obj.target;
         _loc5_ = "trophy";
      }
      _loc2_.blockItem();
      this.createDragItemMc(_loc4_);
      this.currDDOperation = new lol.gpui.DDOperation();
      this.currDDOperation.setFrom(_loc4_,_loc5_,_loc2_);
      this.unselect();
   }
   function createDragItemMc(_item)
   {
      var _loc2_ = "icon";
      if(_loc2_ == "icon")
      {
         this.dragItemMc = lol.gpui.ItemContainer(this.attachMovie("itemCont","dd",10));
         this.dragItemMc.attachIconEnabled = true;
      }
      else if(_loc2_ == "list")
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
   function draggingItem()
   {
      this.dragItemMc._x = Math.round(this._xmouse - this.dragItemMc._width / 2);
      this.dragItemMc._y = Math.round(this._ymouse - this.dragItemMc._height / 2);
   }
   function doubleClick(obj)
   {
      if(!this.ddOperation_arr)
      {
         this.ddOperation_arr = new Array();
      }
      var _loc2_;
      this.currDDOperation = new lol.gpui.DDOperation();
      var _loc5_;
      if(obj.target.item_mc)
      {
         _loc2_ = obj.target.item_mc;
         this.currDDOperation.setFrom(_loc2_.item,obj.target,_loc2_);
         this.currDDOperation.setTo(null,"trophy");
         this.trophyManager.setPublicTrophy(0,this.currDDOperation.fromSlot.data);
      }
      else
      {
         _loc2_ = obj.target;
         this.currDDOperation.setFrom(_loc2_.item,"trophy",_loc2_);
         this.currDDOperation.setTo(this.publicTrophyList_arr[0].item,this.publicTrophyList_arr[0],this.publicTrophyList_arr[0].item_mc);
         this.trophyManager.setPublicTrophy(lol.core.objects.Trophy(this.currDDOperation.fromItem),this.currDDOperation.toSlot.data);
         this.currDDOperation.successOperation();
         _loc5_ = this.publicTrophy_arr;
         for(var _loc3_ in this.publicTrophy_arr)
         {
            if(this.publicTrophy_arr[_loc3_] == this.currDDOperation.fromItem)
            {
               this.trophyManager.setPublicTrophy(0,Number(_loc3_));
               break;
            }
         }
      }
      this.unselect();
   }
   function dropItem(obj)
   {
      var _loc2_;
      if(this.ddFlag)
      {
         _loc2_ = obj.target.item_mc;
         this.currDDOperation.setTo(_loc2_.item,obj.target,_loc2_);
      }
   }
   function onMouseUp()
   {
      var _loc4_;
      var _loc3_;
      var _loc6_;
      var _loc5_;
      var _loc7_;
      if(this.ddFlag)
      {
         this.ddFlag = false;
         this.dragItemMc.kill();
         this.dragItemMc.removeMovieClip();
         _loc4_ = this.trophyListPan._x;
         _loc3_ = this.trophyListPan._y;
         _loc6_ = this.trophyListPan.mask_mc._width;
         _loc5_ = this.trophyListPan.mask_mc._height;
         if(this._xmouse > _loc4_ && this._xmouse < _loc4_ + _loc6_ && this._ymouse > _loc3_ && this._ymouse < _loc3_ + _loc5_)
         {
            this.currDDOperation.setTo(undefined,"trophy");
         }
         else if(this._xmouse > this.delete_btn._x && this._xmouse < this.delete_btn._x + this.delete_btn._width && this._ymouse > this.delete_btn._y && this._ymouse < this.delete_btn._y + this.delete_btn._height)
         {
            this.currDDOperation.setTo(undefined,"delete");
         }
         if(this.currDDOperation.fromSlot == this.currDDOperation.toSlot)
         {
            this.currDDOperation.failedOperation();
         }
         else if(this.currDDOperation.fromSlot == "trophy" && this.currDDOperation.toSlot && this.currDDOperation.toSlot != "delete")
         {
            this.trophyManager.setPublicTrophy(lol.core.objects.Trophy(this.currDDOperation.fromItem),this.currDDOperation.toSlot.data);
            _loc7_ = this.publicTrophy_arr;
            for(var _loc2_ in this.publicTrophy_arr)
            {
               if(this.publicTrophy_arr[_loc2_] == this.currDDOperation.fromItem)
               {
                  this.trophyManager.setPublicTrophy(0,Number(_loc2_));
                  break;
               }
            }
            this.currDDOperation.successOperation();
         }
         else if(this.currDDOperation.toSlot == "trophy" && this.currDDOperation.fromSlot)
         {
            this.trophyManager.setPublicTrophy(0,this.currDDOperation.fromSlot.data);
         }
         else if(this.currDDOperation.fromSlot != "trophy" && this.currDDOperation.toSlot && this.currDDOperation.toSlot != "trophy")
         {
            this.trophyManager.setPublicTrophy(lol.core.objects.Trophy(this.currDDOperation.fromItem),this.currDDOperation.toSlot.data);
            if(this.currDDOperation.toItem)
            {
               this.trophyManager.setPublicTrophy(lol.core.objects.Trophy(this.currDDOperation.toItem),this.currDDOperation.fromSlot.data);
            }
            else
            {
               this.trophyManager.setPublicTrophy(0,this.currDDOperation.fromSlot.data);
            }
            this.currDDOperation.successOperation();
         }
         else if(this.currDDOperation.fromSlot == "trophy" && this.currDDOperation.toSlot == "delete")
         {
            this.unselect();
            this.currSelect = this.currDDOperation.fromItemMc;
            this.deleteTrophy();
         }
         else
         {
            this.currDDOperation.failedOperation();
         }
      }
      delete this.onMouseMove;
   }
   function selectTrophy(obj)
   {
      this.currSelect.toggled = false;
      this.currSelect = lol.gpui.ItemContainer(obj.target);
      this.currSelect.toggled = true;
   }
   function unselect()
   {
      this.currSelect.toggled = false;
      delete this.currSelect;
   }
   function deleteTrophy()
   {
      var _loc2_;
      if(this.currSelect)
      {
         this.currSelect.blockItem();
         _loc2_ = lol.gpui.dialogue.GPUIDialogue(lol.core.SceneShifter.openNewWindow("query").content);
         _loc2_.label = "Удалить трофей?";
         _loc2_.addEventListener("click",this,this._deleteTrophy);
      }
   }
   function _deleteTrophy(obj)
   {
      obj.target.addEventListener("click",this,this._deleteTrophy);
      lol.core.SceneShifter.closeWindow("query");
      if(obj.success)
      {
         this.ddOperation_arr.push(this.currDDOperation);
         this.trophyManager.deleteTrophy(this.currSelect.item);
         this.unselect();
      }
      else
      {
         this.currDDOperation.failedOperation();
         this.currSelect.unblockItem();
      }
   }
   function deleteTrophyAck(obj)
   {
      var _loc2_ = lol.gpui.DDOperation(this.ddOperation_arr.shift());
      if(obj.success)
      {
         _loc2_.successOperation();
         this.setTrophyList();
      }
      else
      {
         _loc2_.failedOperation();
      }
   }
   function sortBy(obj, _sort_str)
   {
      this.setTrophyList();
      var _loc6_ = !_sort_str ? obj.target.data : _sort_str;
      this.sortTrophyList_arr.sortOn(_loc6_);
      var _loc5_ = 0;
      var _loc3_ = 0;
      var _loc2_ = 0;
      var _loc4_;
      while(_loc2_ < this.sortTrophyList_arr.length)
      {
         _loc4_ = this.sortTrophyList_arr[_loc2_].trophy_mc;
         _loc4_._x = _loc3_ * 170;
         _loc4_._y = _loc5_ * 85;
         if(_loc3_ < 2)
         {
            _loc3_ = _loc3_ + 1;
         }
         else
         {
            _loc3_ = 0;
            _loc5_ = _loc5_ + 1;
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function search()
   {
      var _loc7_ = this.search_txt.text.toUpperCase();
      this.cancelSearch_btn._visible = _loc7_.length > 1;
      this.setTrophyList();
      var _loc6_ = 0;
      var _loc3_ = 0;
      var _loc5_;
      var _loc4_;
      var _loc2_;
      for(var _loc8_ in this.sortTrophyList_arr)
      {
         _loc5_ = this.sortTrophyList_arr[_loc8_].search.toUpperCase();
         _loc4_ = _loc5_.indexOf(_loc7_);
         _loc2_ = this.sortTrophyList_arr[_loc8_].trophy_mc;
         if(_loc4_ != -1)
         {
            _loc2_._visible = true;
            _loc2_._x = _loc3_ * 170;
            _loc2_._y = _loc6_ * 85;
            if(_loc3_ < 2)
            {
               _loc3_ = _loc3_ + 1;
            }
            else
            {
               _loc3_ = 0;
               _loc6_ = _loc6_ + 1;
            }
         }
         else
         {
            _loc2_._visible = false;
            _loc2_._x = 0;
            _loc2_._y = 0;
         }
      }
      this.trophyListPan.chekSize();
   }
   function cancelSearch()
   {
      this.search_txt.text = "";
      this.search();
   }
   function pressEscKey()
   {
      if(this.ddFlag)
      {
         this.ddFlag = false;
         this.dragItemMc.kill();
         this.dragItemMc.removeMovieClip();
         this.currDDOperation.fromItemMc.unblockItem();
         delete this.onMouseMove;
         delete this.currDDOperation;
      }
      else
      {
         this.cancel();
      }
   }
}
