class lol.gpui.TransRentInterface extends lol.gpui.StaffInterface
{
   var _xmouse;
   var _ymouse;
   var attachMovie;
   var bagInfo_txt;
   var close_btn;
   var cost_label_txt;
   var cost_txt;
   var curSlot;
   var currDDOperation;
   var dir;
   var dispatchEvent;
   var doLater;
   var dragCont;
   var dragItemMc;
   var dragNdrop;
   var gMoneyPan;
   var gamer;
   var hBar;
   var heapSepItem;
   var info_txt;
   var leftNum;
   var lessor;
   var master;
   var moneyPan;
   var newSlot;
   var onEnterFrame;
   var onMouseMove;
   var priceEnabled;
   var rent_btn;
   var rightNum;
   var slots;
   var tf;
   var time_txt;
   var transport_mc;
   var maxValue = 365;
   var ddFlag = false;
   var pause = 10;
   var count = 0;
   function TransRentInterface()
   {
      super();
      this.tf = new TextFormat();
      this.tf.bold = true;
      this.doLater("init");
      this.slots = new Array();
      this.slots.transport = this.transport_mc;
      this.slots.newSlot = this.newSlot;
      this.slots.curSlot = this.curSlot;
      this.transport_mc.id = "transport";
      this.newSlot.id = "newSlot";
      this.curSlot.id = "curSlot";
      this.master = lol.core.Master.getInstance();
      this.gamer = this.master.gamer;
      var _loc3_ = this.gamer.rent.lessorID;
      this.lessor = lol.core.player.Lessor(this.master.getPlayer(_loc3_));
   }
   function init()
   {
      this.time_txt.onChanged = mx.utils.Delegate.create(this,this.changedLeft);
      this.time_txt.restrict = "0-9";
      this.transport_mc.alignEnabled = false;
      this.transport_mc.bagPan.setSize(185,337);
      this.transport_mc.showPriseInGold = true;
      this.transport_mc.priceEnabled = true;
      this.transport_mc.dragEnabled = true;
      this.transport_mc.selectGroupAvailable = false;
      this.dragEnabled = true;
      this.hBar.setPosition(0);
      this.rightNum = 1;
      this.moneyPan.type = "afro";
      this.gMoneyPan.type = "gold";
      this.gamer.addEventListener(lol.events.PlayerEvent.UPDATE_INFO,this,this.userInfoUpdate);
      this.userInfoUpdate();
      this.transport_mc.addEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.transport_mc.addEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.transport_mc.addEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.newSlot.addEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.hBar.setSize(129);
      this.hBar.setPosition(0);
      this.hBar.addEventListener("position",this);
      this.hBar.upButton.addEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this,this.scrUp);
      this.hBar.downButton.addEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this,this.scrDown);
      this.hBar.upButton.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.scrUp_up);
      this.hBar.downButton.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.scrDown_up);
      this.hBar.upButton.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_OUTSIDE_EVENT,this,this.scrUp_up);
      this.hBar.downButton.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_OUTSIDE_EVENT,this,this.scrDown_up);
      this.hBar.upButton.removeEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this.hBar,this.hBar.scrollUp);
      this.hBar.upButton.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this.hBar,this.hBar.stopScroll);
      this.hBar.downButton.removeEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this.hBar,this.hBar.scrollDown);
      this.hBar.downButton.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this.hBar,this.hBar.stopScroll);
      this.close_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.rent_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.getTransport);
      this.doLater("initObjects");
      var _loc2_ = this.gamer.playerInfo.transRentTime;
      var _loc3_ = this.gamer.playerInfo.transport;
      if(_loc3_ && _loc2_ != undefined)
      {
         if(_loc2_ > 24)
         {
            this.info_txt.text = "Оставшееся время: " + Math.floor(_loc2_ / 24) + " дн. " + _loc2_ % 24 + " ч.";
         }
         else
         {
            this.info_txt.text = "Оставшееся время: " + _loc2_ + " ч.";
         }
         this.curSlot.addItem(_loc3_);
      }
      else
      {
         this.info_txt.text = "У вас нет транспорта";
      }
      this.info_txt.setTextFormat(this.tf);
      lol.core.SceneShifter.hotKeyManager.addFilter("transport");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.ESC,this,this.close);
   }
   function kill()
   {
      this.transport_mc.removeEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.transport_mc.removeEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.transport_mc.removeEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.newSlot.removeEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.hBar.upButton.removeEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this,this.scrUp);
      this.hBar.downButton.removeEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this,this.scrDown);
      this.hBar.upButton.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.scrUp_up);
      this.hBar.downButton.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.scrDown_up);
      this.hBar.upButton.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_OUTSIDE_EVENT,this,this.scrUp_up);
      this.hBar.downButton.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_OUTSIDE_EVENT,this,this.scrDown_up);
      this.close_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.rent_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.getTransport);
      lol.core.SceneShifter.hotKeyManager.removeFilter("transport");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.ESC,this,this.close);
   }
   function close()
   {
      this.gamer.rent.close();
      this.dispatchEvent({type:"closeWindow"});
   }
   function initObjects()
   {
      var _loc3_ = this.lessor.transArray;
      var _loc2_;
      for(var _loc6_ in _loc3_)
      {
         _loc2_ = _loc3_[_loc6_];
         this.addItem({slot:this.transport_mc,item:_loc2_});
      }
      this.bagInfo_txt.text = String(_loc3_.length);
      this.bagInfo_txt.setTextFormat(this.tf);
   }
   function userInfoUpdate(obj)
   {
      var _loc3_ = lol.core.Master.getInstance();
      var _loc5_ = _loc3_.gamer.attributes.afro;
      var _loc6_ = _loc3_.gamer.attributes.gold;
      this.showMoney(_loc5_,_loc6_);
      var _loc4_ = this.gamer.playerInfo.transport;
      var _loc2_ = this.gamer.playerInfo.transRentTime;
      if(_loc4_ && _loc2_ != undefined)
      {
         this.curSlot.addItem(_loc4_);
         if(_loc2_ > 24)
         {
            this.info_txt.text = "Оставшееся время: " + Math.floor(_loc2_ / 24) + " дн. " + _loc2_ % 24 + " ч.";
         }
         else
         {
            this.info_txt.text = "Оставшееся время: " + _loc2_ + " ч.";
         }
         this.info_txt.setTextFormat(this.tf);
      }
   }
   function showMoney(afro, gold)
   {
      this.moneyPan.value = afro;
      this.gMoneyPan.value = gold;
   }
   function startDragNDrop(obj)
   {
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
   function draggingItem()
   {
      this.dragItemMc._x = Math.round(this._xmouse - this.dragItemMc._width / 2);
      this.dragItemMc._y = Math.round(this._ymouse - this.dragItemMc._height / 2);
   }
   function doubleClick(obj)
   {
      var _loc2_ = obj.item_mc;
      _loc2_.blockItem();
      this.currDDOperation = new lol.gpui.DDOperation();
      this.currDDOperation.setFrom(_loc2_.item,obj.target,_loc2_);
      this.currDDOperation.setTo(0,this.newSlot);
      this.sendTransferToServer();
   }
   function dropItem(obj)
   {
      var _loc2_;
      if(this.ddFlag)
      {
         _loc2_ = obj.target;
         this.currDDOperation.setTo(0,_loc2_);
      }
   }
   function onMouseUp()
   {
      if(this.ddFlag)
      {
         this.ddFlag = false;
         this.dragItemMc.kill();
         this.dragItemMc.removeMovieClip();
         if(this.currDDOperation.toSlot && this.currDDOperation.toSlot != this.transport_mc)
         {
            this.sendTransferToServer();
         }
         else
         {
            this.currDDOperation.failedOperation();
            delete this.currDDOperation;
         }
      }
      delete this.onMouseMove;
   }
   function sendTransferToServer()
   {
      this.currDDOperation.toSlot.addItem(this.currDDOperation.fromItem);
      this.currDDOperation.successOperation();
      if(this.currDDOperation.fromItem.getProp("g_cost"))
      {
         this.cost_label_txt.text = "Цена (G)";
      }
      else
      {
         this.cost_label_txt.text = "Цена (Афро)";
      }
      this.cost_label_txt.setTextFormat(this.tf);
      this.printTxt();
      delete this.currDDOperation;
   }
   function selectItem(obj)
   {
      var _loc2_ = obj.item;
      if(_loc2_)
      {
         this.newSlot.addItem(_loc2_);
         if(_loc2_.getProp("g_cost"))
         {
            this.cost_label_txt.text = "Цена (G)";
         }
         else
         {
            this.cost_label_txt.text = "Цена (Афро)";
         }
         this.cost_label_txt.setTextFormat(this.tf);
      }
      this.printTxt();
   }
   function getTransport()
   {
      var _loc2_;
      var _loc3_;
      var _loc4_;
      if(this.newSlot.item_mc.item)
      {
         if(Number(this.time_txt.text))
         {
            _loc2_ = this.newSlot.item_mc.item.getProp("premium");
            if(_loc2_ > lol.core.Master.getInstance().gamer.premium)
            {
               if(_loc2_ == 1)
               {
                  _loc3_ = "У вас должен быть вид на жительство";
               }
               else if(_loc2_ == 2)
               {
                  _loc3_ = "У вас должно быть гражданство";
               }
               this.newAlert(_loc3_);
            }
            else if(!this.gamer.playerInfo.transport || this.gamer.playerInfo.transRentTime == undefined)
            {
               this._getTransport(this.newSlot.item_mc.item);
            }
            else
            {
               _loc4_ = this.newDialogue("У вас уже есть арендованный транспорт. Вы хотите его поменять?");
               _loc4_.addEventListener("click",this,this.newTransAck);
               this.transport_mc.removeEventListener("_mouseUp",this,this.selectItem);
            }
         }
         else
         {
            this.newAlert("Надо выбрать срок аренды");
         }
      }
      else
      {
         this.newAlert("Сперва надо выбрать транспорт");
      }
   }
   function _getTransport(transObj)
   {
      this.gamer.rent.addEventListener(lol.core.transport.TransEvent.GET_TRANSPORT_SUCCESS,this,this.getTransportAck);
      this.gamer.rent.addEventListener(lol.core.transport.TransEvent.GET_TRANSPORT_FAIL,this,this.getTransportAck);
      this.gamer.rent.getTransport(this.newSlot.item_mc.item.typeID,Number(this.time_txt.text));
   }
   function getTransportAck(obj)
   {
      this.gamer.rent.removeEventListener(lol.core.transport.TransEvent.GET_TRANSPORT_SUCCESS,this,this.getTransportAck);
      this.gamer.rent.removeEventListener(lol.core.transport.TransEvent.GET_TRANSPORT_FAIL,this,this.getTransportAck);
      var _loc2_ = obj.type;
      if(_loc2_ == lol.core.transport.TransEvent.GET_TRANSPORT_SUCCESS)
      {
         this.newAlert("Вы арендовали траспорт " + this.newSlot.item_mc.item.getProp("name") + " на срок " + this.time_txt.text + " дн.");
         this.newSlot.item_mc.removeMovieClip();
         this.rightNum = 1;
         this.hBar.setPosition(0);
      }
      else
      {
         this.newAlert("У вас недостаточно денег");
      }
   }
   function newTransAck(obj)
   {
      obj.target.removeEventListener("click",this,this.newTransAck);
      lol.core.SceneShifter.closeWindow("query");
      this.transport_mc.addEventListener("_mouseUp",this,this.selectItem);
      var _loc2_ = obj.success;
      if(_loc2_)
      {
         this._getTransport();
      }
   }
   function newDialogue(str)
   {
      var _loc1_ = lol.core.SceneShifter.openNewWindow("query");
      _loc1_.content.label = str;
      return _loc1_.content;
   }
   function newAlert(str)
   {
      var _loc1_ = lol.core.SceneShifter.openNewWindow("alert");
      _loc1_.content.label = str;
   }
   function position(obj)
   {
      var _loc2_ = obj.pos <= 100 ? obj.pos : 100;
      this.rightNum = Math.round(this.maxValue * _loc2_ / 100);
      this.rightNum = this.rightNum != 0 ? this.rightNum : 1;
      this.leftNum = this.maxValue - this.rightNum;
      this.printTxt();
   }
   function printTxt()
   {
      this.time_txt.text = String(this.rightNum);
      var _loc3_;
      var _loc2_;
      if(this.newSlot.item_mc.item)
      {
         _loc3_ = this.newSlot.item_mc.item.getProp("cost");
         _loc2_ = this.newSlot.item_mc.item.getProp("g_cost");
         if(_loc2_)
         {
            this.cost_txt.text = String(_loc2_ * this.rightNum / 100);
         }
         else
         {
            this.cost_txt.text = String(_loc3_ * this.rightNum);
         }
      }
      else
      {
         this.cost_txt.text = "";
      }
      this.time_txt.setTextFormat(this.tf);
      this.cost_txt.setTextFormat(this.tf);
   }
   function scrollEnterFrame()
   {
      if(this.count >= this.pause)
      {
         if(this.dir != 0)
         {
            this.scrollOnStep();
         }
         else
         {
            delete this.onEnterFrame;
            this.count = 0;
         }
      }
      else if(this.count == 0)
      {
         this.scrollOnStep();
         this.count = this.count + 1;
      }
      else
      {
         this.count = this.count + 1;
      }
   }
   function scrollOnStep()
   {
      if(this.dir > 0)
      {
         if(this.leftNum > 0)
         {
            this.rightNum = this.rightNum + 1;
         }
      }
      else if(this.dir < 0)
      {
         if(this.leftNum < this.maxValue - 1)
         {
            this.rightNum = this.rightNum - 1;
         }
      }
      this.leftNum = this.maxValue - this.rightNum;
      this.hBar.position(this.pos);
      this.printTxt();
   }
   function scrUp(obj)
   {
      this.hBar.removeEventListener("position",this);
      this.dir = -1;
      this.count = 0;
      this.onEnterFrame = mx.utils.Delegate.create(this,this.scrollEnterFrame);
   }
   function scrUp_up()
   {
      this.hBar.addEventListener("position",this);
      this.dir = 0;
   }
   function scrDown(obj)
   {
      this.hBar.removeEventListener("position",this);
      this.dir = 1;
      this.count = 0;
      this.onEnterFrame = mx.utils.Delegate.create(this,this.scrollEnterFrame);
   }
   function scrDown_up()
   {
      this.hBar.addEventListener("position",this);
      this.dir = 0;
   }
   function get pos()
   {
      var _loc2_ = new Object();
      var _loc3_ = this.rightNum / this.maxValue * 100;
      _loc2_.pos = _loc3_;
      return _loc2_;
   }
   function changedLeft()
   {
      if(this.time_txt.text == "")
      {
         this.time_txt.text = "1";
      }
      if(Number(this.time_txt.text) > this.maxValue)
      {
         this.time_txt.text = String(this.maxValue);
      }
      if(Number(this.time_txt.text) < 1)
      {
         this.time_txt.text = String(1);
      }
      this.rightNum = Number(this.time_txt.text);
      this.leftNum = this.maxValue - this.rightNum;
      this.printTxt();
      this.hBar.position(this.pos);
   }
   function __drop()
   {
      if(this.dragNdrop.from.id == "transport" && this.dragNdrop.where.id == "newSlot")
      {
         this.selectItem({item:this.dragNdrop.what[0].item});
      }
      else if(this.dragNdrop.from.id == "transport" && this.dragNdrop.where.id == "curSlot")
      {
         this.selectItem({item:this.dragNdrop.what[0].item});
      }
      this.transport_mc.addItem(this.dragNdrop.what[0].item);
      this.dragCont.kill();
      this.dragCont.removeMovieClip();
      delete this.dragNdrop;
      delete this.dragCont.onMouseMove;
      this.dragCont.removeMovieClip();
      this.dragON = false;
      this.dragCont = null;
      this.heapSepItem = null;
      this.dropEnabled = true;
      this.printTxt();
   }
}
