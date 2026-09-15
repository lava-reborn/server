class lol.gpui.ItemContainer extends lol.gpui.GPUIObject
{
   var __item;
   var _height;
   var _parent;
   var _width;
   var _xmouse;
   var _ymouse;
   var amount_mc;
   var attachMovie;
   var bg_mc;
   var breakBar;
   var clickTimer;
   var costType;
   var createEmptyMovieClip;
   var dispatchEvent;
   var fireArm_mod_mc;
   var format;
   var getNextHighestDepth;
   var iconCont_mc;
   var icon_mc;
   var info_btn;
   var mainCost;
   var modeType_txt;
   var name_txt;
   var onMouseMove;
   var premium_mc;
   var price_mc;
   var reload_btn;
   var annotationPause = 0;
   var _toggled = false;
   var attachBackEnabled = true;
   var attachIconEnabled = true;
   var groupItem = false;
   var showPriseInGold = false;
   var showHeapCount = true;
   var showItemRepairMod = false;
   var showItemSellMod = false;
   static var START_DRAG_N_DROP = "START_DRAG_N_DROP";
   static var DOUBLE_CLICK = "DOUBLE_CLICK";
   static var SELECT = "SELECT";
   static var MOUSE_UP_ON_THIS = "MOUSE_UP_ON_THIS";
   static var DROP = "DROP";
   static var SEPARATE_HEAP = "SEPARATE_HEAP";
   static var RELOAD = "RELOAD";
   static var SHIFT_SELECT = "SHIFT_SELECT";
   static var CTRL_SELECT = "CTRL_SELECT";
   var blockFlag = false;
   var priceEnabled = false;
   var rollOverFlag = false;
   var cost_mod = 1;
   var enabled = true;
   var clickFlag = false;
   function ItemContainer()
   {
      super();
      this.bg_mc.onPress = mx.utils.Delegate.create(this,this.onPressBg);
      this.bg_mc.onRelease = mx.utils.Delegate.create(this,this.onReleaseBg);
      this.bg_mc.onRollOver = mx.utils.Delegate.create(this,this.rollOverBack);
      this.bg_mc.onRollOut = mx.utils.Delegate.create(this,this.rollOutBack);
      this.bg_mc.onReleaseOutside = mx.utils.Delegate.create(this,this.rollOutBack);
      this.reload_btn.onPress = mx.utils.Delegate.create(this,this.onReload);
      this.reload_btn._visible = false;
      this.breakBar._visible = false;
      this.doLater("init");
      this.format = new TextFormat();
      this.format.bold = true;
   }
   function init()
   {
      var _loc2_ = this._parent._parent._parent;
      _loc2_.addEventListener("enabledContent",this);
   }
   function kill()
   {
      var _loc2_ = this._parent._parent._parent;
      _loc2_.removeEventListener("enabledContent",this);
      lol.gpui.AnnotationManager.clear();
   }
   function enabledContent(obj)
   {
      this.enabled = obj.status;
   }
   function onReload()
   {
      this.dispatch({type:lol.gpui.ItemContainer.RELOAD});
   }
   function onPressBg()
   {
      lol.gpui.AnnotationManager.clear();
      lol.gpui.HintManager.closeHint();
      delete this.price_mc.onMouseMove;
      this.onMouseMove = this.startDragNDrop;
   }
   function onReleaseBg()
   {
      if(this.clickFlag)
      {
         this.dispatch({type:lol.gpui.ItemContainer.DOUBLE_CLICK});
         this.clickFlag = false;
         delete this.clickTimer;
      }
      else
      {
         this.clickFlag = true;
         this.clickTimer = new lol.utils.Timeout(this,this.endOfTimer,400);
      }
      if(Key.isDown(16))
      {
         this.dispatch({type:lol.gpui.ItemContainer.SHIFT_SELECT});
      }
      else if(Key.isDown(17))
      {
         this.dispatch({type:lol.gpui.ItemContainer.CTRL_SELECT});
      }
      else
      {
         this.dispatch({type:lol.gpui.ItemContainer.SELECT});
      }
      lol.gpui.AnnotationManager.clear();
      delete this.onMouseMove;
      delete this.price_mc.onMouseMove;
   }
   function endOfTimer()
   {
      this.clickFlag = false;
      delete this.clickTimer;
   }
   function onMouseUp()
   {
      if(this._xmouse > 0 && this._ymouse > 0 && this._xmouse < this._width && this._ymouse < this._height)
      {
         this.dispatch({type:lol.gpui.ItemContainer.MOUSE_UP_ON_THIS});
      }
   }
   function rollOverBack()
   {
      this.rollOverFlag = true;
      if(this.enabled)
      {
         this.toggled_frame = true;
      }
      this.dispatch({type:"_onMouseOver"});
      if(!this.blockFlag)
      {
         lol.gpui.AnnotationManager.create(this.__item,this._xmouse,this.bg_mc._width - this._xmouse,this._ymouse);
      }
      if(this.priceEnabled)
      {
         this.price_mc.onMouseMove = mx.utils.Delegate.create(this,this.priceMove);
      }
   }
   function rollOutBack()
   {
      this.rollOverFlag = false;
      this.toggled_frame = this.toggled;
      this.dispatch({type:"_onMouseOut"});
      lol.gpui.AnnotationManager.clear();
      delete this.price_mc.onMouseMove;
   }
   function priceMove()
   {
      if(this._xmouse > this.price_mc._x && this._xmouse < this.price_mc._x + this.price_mc._width && this._ymouse > this.price_mc._y && this._ymouse < this.price_mc._y + this.price_mc._height)
      {
         lol.gpui.HintManager.showHint(this.costType,this.price_mc._ymouse,this.price_mc._height - this.price_mc._ymouse);
      }
      else
      {
         lol.gpui.HintManager.closeHint();
      }
   }
   function startDragNDrop()
   {
      delete this.onMouseMove;
      this.toggled_frame = false;
      if(Key.isDown(17) && this.item instanceof lol.core.objects.Heapable)
      {
         this.dispatch({type:lol.gpui.ItemContainer.SEPARATE_HEAP});
      }
      else
      {
         this.dispatch({type:lol.gpui.ItemContainer.START_DRAG_N_DROP});
      }
   }
   function blockItem()
   {
      lol.utils.SaturationManager.setSaturation(this,0);
      this.blockFlag = true;
      this.bg_mc.useHandCursor = false;
   }
   function unblockItem()
   {
      lol.utils.SaturationManager.setSaturation(this,100);
      this.blockFlag = false;
      this.bg_mc.useHandCursor = true;
   }
   function dispatch(obj)
   {
      if(!this.blockFlag)
      {
         this.dispatchEvent(obj);
      }
   }
   function attachIcon(item)
   {
      this.showBreakAlert(false);
      this.__item = item;
      var _loc15_ = item.id;
      var _loc6_ = item.typeID;
      var _loc4_ = item.rootID;
      if(item.getProp("premium"))
      {
         this.premium_mc.gotoAndStop(item.getProp("premium") + 1);
      }
      if(_loc4_ == lol.core.objects.Item.TROPHY)
      {
         this.attachIconEnabled = !lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.CRUEL_TROPHY) && this.attachIconEnabled;
      }
      var _loc10_;
      var _loc13_;
      if(this.attachIconEnabled)
      {
         this.iconCont_mc.removeMovieClip();
         this.iconCont_mc = this.createEmptyMovieClip("iconCont_mc",this.getNextHighestDepth());
         if(this.__item.rootID == lol.core.transport.TransObject.TRANSPORT)
         {
            _loc13_ = this.__item.getProp("res");
            _loc10_ = lol.services.SSEmulator.getTransportIcon(_loc13_);
            _loc6_ += "_transport";
         }
         else
         {
            _loc10_ = lol.services.SSEmulator.getIcon(_loc6_);
         }
         this.icon_mc = lol.display.DisplaySprite.create(this.iconCont_mc,"icon_mc",0);
         this.icon_mc.display(_loc6_ + "_icon",_loc10_);
      }
      if(this.attachBackEnabled)
      {
         if(item.getProp("quest"))
         {
            this.attachBack(lol.core.objects.Item.QUEST);
         }
         else
         {
            this.attachBack(_loc4_);
         }
      }
      if(item.rootID == lol.core.objects.Item.FIRE_ARM || item.rootID == lol.core.objects.Item.WEAR || item.rootID == lol.core.objects.Item.COLD_ARM)
      {
         this.name_txt._y -= 1;
         this.breakBar._visible = true;
         this.doLater("showBreak",[item]);
      }
      var _loc7_;
      var _loc3_;
      var _loc8_;
      var _loc11_;
      var _loc12_;
      if(item.rootID == lol.core.objects.Item.AMMO && this.attachBackEnabled)
      {
         _loc7_ = item.getProp("mod_type");
         if(_loc7_)
         {
            _loc3_ = this.attachMovie("mod_mc","mod_mc",this.getNextHighestDepth());
            _loc3_.gotoAndStop(_loc7_);
            _loc3_._x = 135;
            if(this.attachIconEnabled)
            {
               _loc3_._y = 64;
            }
            else
            {
               _loc3_._y = 18;
            }
         }
         _loc8_ = item.getProp("size");
         _loc11_ = item.getProp("max_count");
         _loc12_ = _loc8_ != undefined ? _loc8_ : _loc11_;
         this.doLater("showAmount",[_loc12_]);
      }
      var _loc9_;
      if(item.rootID != lol.core.objects.Item.WEAR)
      {
         _loc9_ = !item.getProp("sub_name") ? "" : item.getProp("sub_name");
         this.modeType_txt.text = _loc9_.toUpperCase();
      }
      if(item.rootID == lol.core.objects.Item.TROPHY)
      {
         _loc9_ = item.getProp("v_name");
         if(_loc9_)
         {
            this.modeType_txt.text = _loc9_.toUpperCase();
         }
      }
      if(item.rootID == lol.core.objects.Item.FIRE_ARM)
      {
         if(this.attachBackEnabled)
         {
            this.attachAmmoMode();
         }
      }
      var _loc5_;
      if(this.priceEnabled && this.attachBackEnabled)
      {
         _loc5_ = this.getNextHighestDepth();
         if(this.attachIconEnabled)
         {
            this.price_mc = this.attachMovie("priceItem","priceItem" + _loc5_,_loc5_);
            this.price_mc._x = 7;
            this.price_mc._y = 3;
            this.doLater("showCost",[item,"center"]);
         }
         else
         {
            this.price_mc = this.createEmptyMovieClip("priceItem",_loc5_);
            this.price_mc.attachMovie("textCharCreate","fontContainer",this.price_mc.getNextHighestDepth());
            this.price_mc._x = 10;
            this.price_mc._y = 7;
            this.doLater("showCost",[item,"left"]);
         }
      }
      var _loc14_;
      if(item.inited)
      {
         _loc14_ = item.getProp("name") == "0" ? "" : item.getProp("name");
         this.name_txt.text = _loc14_.toUpperCase();
         this.name_txt.setTextFormat(this.format);
      }
      else
      {
         this.name_txt.text = "ЗАГРУЖАЕТСЯ...";
         this.name_txt.setTextFormat(this.format);
      }
      if(_loc4_ == lol.core.objects.Item.TROPHY && lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.CRUEL_TROPHY))
      {
         this.name_txt.text = "ТРОФЕЙ";
      }
      item.addEventListener("itemUpdate",this);
   }
   function attachAmmoMode()
   {
      this.fireArm_mod_mc.removeMovieClip();
      this.fireArm_mod_mc = this.attachMovie("fireArm_mod_mc","mod_mc",this.getNextHighestDepth());
      this.fireArm_mod_mc._x = 139;
      this.amount_mc._x = 135;
      if(this.attachIconEnabled)
      {
         this.fireArm_mod_mc._y = 52;
      }
      else
      {
         this.fireArm_mod_mc._y = 6;
      }
      var _loc8_ = this.__item;
      var _loc5_ = lol.core.Master.getInstance().gamer.equipment.getAmmo(_loc8_);
      var _loc7_ = _loc8_.getProp("ammoType");
      var _loc3_;
      var _loc2_;
      var _loc6_;
      var _loc4_;
      if(_loc7_)
      {
         _loc3_ = 0;
         while(_loc3_ < _loc5_.length)
         {
            _loc2_ = _loc5_[_loc3_];
            _loc2_.removeEventListener("itemUpdate",this,this.attachAmmoMode);
            if(_loc2_.inited)
            {
               _loc6_ = _loc2_.getProp("mod_type");
               if(_loc2_.typeID == _loc7_)
               {
                  _loc4_ = _loc2_.getProp("mod_type");
                  this.fireArm_mod_mc.gotoAndStop(_loc4_);
               }
            }
            else
            {
               _loc2_.addEventListener("itemUpdate",this,this.attachAmmoMode);
            }
            _loc3_ = _loc3_ + 1;
         }
      }
      else
      {
         this.fireArm_mod_mc.gotoAndStop(8);
      }
   }
   function showCost(item, align)
   {
      var _loc6_ = this.cost_mod;
      var _loc15_ = item.getProp("repair_mod");
      if(this.showItemRepairMod && _loc15_ != null)
      {
         _loc6_ *= _loc15_;
      }
      var _loc14_ = item.getProp("sell_mod");
      if(this.showItemSellMod && _loc14_ != null)
      {
         _loc6_ *= _loc14_;
      }
      var _loc9_ = 1;
      if(item instanceof lol.core.objects.Breakable)
      {
         if(lol.gpui.StaffInterface.ssType == lol.gpui.StaffInterface.SS_TRADE)
         {
            _loc9_ = lol.core.objects.Breakable(item).getCurQuality();
         }
         else if(lol.gpui.StaffInterface.ssType == lol.gpui.StaffInterface.SS_REPAIR)
         {
            _loc9_ = 1 - lol.core.objects.Breakable(item).getCurQuality();
         }
      }
      var _loc5_ = this.__item.getProp("cost");
      var _loc4_ = this.__item.getProp("g_cost");
      var _loc11_ = this.__item.getProp("bg_p_cost");
      var _loc7_;
      if(this.showHeapCount)
      {
         _loc7_ = item.getProp("size");
         if(_loc7_)
         {
            _loc5_ = item.getProp("cost") * _loc7_;
            _loc4_ = item.getProp("g_cost") * _loc7_;
            _loc11_ = item.getProp("bg_p_cost") * _loc7_;
         }
      }
      var _loc13_;
      var _loc10_;
      if(item instanceof lol.core.objects.HealItem)
      {
         _loc13_ = item.getProp("use_count");
         _loc10_ = item.getProp("max_use_count");
         if(_loc10_)
         {
            _loc5_ = Math.round(_loc5_ * _loc13_ / _loc10_);
            _loc4_ = Math.round(_loc4_ * _loc13_ / _loc10_);
         }
      }
      var _loc3_;
      if(this.__item.rootID == lol.core.transport.TransObject.TRANSPORT)
      {
         _loc5_ = item.cost;
         _loc4_ = item.g_cost;
      }
      this.costType = "Афро";
      if(_loc11_)
      {
         this.price_mc.gotoAndStop(3);
         _loc3_ = _loc11_;
         this.costType = "ПвП-баллы";
      }
      else if(this.showPriseInGold)
      {
         if(_loc4_ != undefined && _loc4_ != 0 && !isNaN(_loc4_))
         {
            this.price_mc.gotoAndStop(2);
            _loc3_ = Math.floor(_loc4_);
            _loc3_ = Number(_loc3_ / 100);
            this.costType = "Золото";
         }
         else
         {
            _loc3_ = Math.floor(_loc5_ * _loc6_);
            this.price_mc.gotoAndStop(1);
         }
      }
      else
      {
         _loc3_ = Math.floor(_loc5_ * _loc6_ * _loc9_);
      }
      if(!_loc3_)
      {
         _loc3_ = 1;
      }
      this.mainCost = _loc3_;
      var _loc8_ = this.price_mc.fontContainer;
      _loc8_.attachText = "priceFont";
      _loc8_.alignText = align;
      _loc8_.letterSpace = -1;
      var _loc12_ = _loc3_;
      if(!this.attachIconEnabled)
      {
         if(_loc4_ != undefined && _loc4_ != 0 && this.showPriseInGold)
         {
            _loc12_ = "g" + _loc3_;
         }
         else
         {
            _loc12_ = "a" + _loc3_;
         }
      }
      _loc8_.showValue(_loc12_);
   }
   function showBreak(item)
   {
      var _loc4_ = item.getProp("__break");
      var _loc2_ = item.getProp("max_break_cur");
      var _loc6_ = Math.round(_loc4_ * 100 / _loc2_);
      var _loc7_ = 101 - _loc6_;
      this.breakBar.bar_mc.gotoAndStop(_loc7_);
      var _loc5_ = item.getProp("max_break_abs");
      var _loc3_ = Math.round(_loc2_ * 100 / _loc5_);
      if(_loc3_ <= 100)
      {
         this.breakBar.bar_mc._xscale = _loc3_;
      }
      else
      {
         this.breakBar.bar_mc._xscale = 100;
      }
      if(_loc4_ == 0)
      {
         this.showBreakAlert(true);
      }
   }
   function showBreakAlert(b)
   {
      this.breakBar.alert_mc._visible = b;
      if(b)
      {
         this.breakBar.bar_mc.alert_mc.play();
      }
      else
      {
         this.breakBar.bar_mc.alert_mc.gotoAndStop(1);
      }
   }
   function showAmount(str)
   {
      if(this.showHeapCount)
      {
         this.amount_mc.attachText = "numChar";
         this.amount_mc.alignText = "right";
         this.amount_mc.letterSpace = -3;
         this.amount_mc.showValue(str);
      }
   }
   function itemUpdate(obj)
   {
      var _loc2_ = this.item.rootID;
      if(this.item.getProp("premium"))
      {
         this.premium_mc.gotoAndStop(this.item.getProp("premium") + 1);
      }
      var _loc13_ = this.item.getProp("name") == "0" ? "" : this.item.getProp("name");
      this.name_txt.text = _loc13_.toUpperCase();
      this.name_txt.setTextFormat(this.format);
      if(_loc2_ == lol.core.objects.Item.TROPHY && lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.CRUEL_TROPHY))
      {
         this.name_txt.text = "ТРОФЕЙ";
      }
      var _loc5_;
      if(_loc2_ != lol.core.objects.Item.WEAR)
      {
         _loc5_ = !this.item.getProp("sub_name") ? "" : this.item.getProp("sub_name");
         this.modeType_txt.text = _loc5_.toUpperCase();
      }
      var _loc10_;
      var _loc8_;
      var _loc6_;
      var _loc12_;
      var _loc11_;
      var _loc3_;
      var _loc7_;
      var _loc4_;
      var _loc9_;
      if(this.item.rootID == lol.core.objects.Item.TROPHY)
      {
         _loc5_ = this.item.getProp("v_name");
         if(_loc5_)
         {
            this.modeType_txt.text = _loc5_.toUpperCase();
         }
         _loc10_ = this.item.getProp("count");
         this.doLater("showAmount",[_loc10_]);
      }
      else if(_loc2_ == lol.core.objects.Item.FIRE_ARM)
      {
         _loc8_ = this.item.getProp("ammo_count");
         _loc6_ = this.item.getProp("clip_size");
         _loc12_ = _loc8_ != undefined ? _loc8_ : "";
         _loc11_ = _loc6_ != undefined ? _loc6_ : "";
         _loc10_ = _loc12_ + "/" + _loc11_;
         this.doLater("showAmount",[_loc10_]);
         if(this.attachBackEnabled)
         {
            this.attachAmmoMode();
         }
      }
      else if(_loc2_ != lol.core.objects.Item.WEAR)
      {
         if(_loc2_ == lol.core.objects.Item.HEAL_ITEM)
         {
            _loc3_ = this.item.getProp("use_count");
            _loc7_ = this.item.getProp("max_use_count");
            _loc12_ = _loc3_ != undefined ? _loc3_ : "";
            _loc11_ = _loc7_ != undefined ? _loc7_ : "";
            _loc10_ = _loc12_ + "/" + _loc11_;
            this.doLater("showAmount",[_loc10_]);
         }
         else if(this.item instanceof lol.core.objects.Heapable || _loc2_ == lol.core.objects.Item.AMMO)
         {
            _loc4_ = this.item.getProp("size");
            _loc9_ = this.item.getProp("max_count");
            _loc10_ = _loc4_ != undefined ? _loc4_ : _loc9_;
            this.doLater("showAmount",[_loc10_]);
         }
      }
      if(this.priceEnabled)
      {
         if(this.attachIconEnabled)
         {
            this.doLater("showCost",[this.item,"center"]);
         }
         else
         {
            this.doLater("showCost",[this.item,"left"]);
         }
      }
   }
   function set item(itm)
   {
      this.__item = itm;
      this.itemUpdate();
   }
   function get item()
   {
      return this.__item;
   }
   function attachBack(bID)
   {
      var _loc2_;
      switch(bID)
      {
         case lol.core.objects.Item.HEAL_ITEM:
            _loc2_ = "medikKitBG";
            break;
         case lol.core.objects.Item.FIRE_ARM:
            _loc2_ = "fireArmBG";
            break;
         case lol.core.objects.Item.AMMO:
            _loc2_ = "ammoBG";
            break;
         case lol.core.objects.Item.TRASH:
            _loc2_ = "trashBG";
            break;
         case lol.core.objects.Item.TROPHY:
            _loc2_ = "trophyBG";
            break;
         case lol.core.objects.Item.QUEST:
            _loc2_ = "questBG";
            break;
         case lol.core.objects.Item.WEAR:
            _loc2_ = "wearBG";
            break;
         case lol.core.objects.Item.COLD_ARM:
            _loc2_ = "fireArmBG";
            break;
         case "small":
            _loc2_ = "wearBG";
            break;
         default:
            _loc2_ = "fireArmBG";
      }
      var _loc3_ = this.item.getProp("premium");
      var _loc6_;
      if(_loc3_ == 1 || _loc3_ == 2)
      {
         _loc2_ += "_premium";
      }
      else
      {
         _loc6_ = this.item.getProp("g_cost");
         if(_loc6_)
         {
            _loc2_ += "_gold";
         }
      }
      this.bg_mc.attachMovie(_loc2_,"bg",0);
      var _loc5_;
      var _loc4_;
      if(this.groupItem)
      {
         _loc5_ = this.bg_mc.attachMovie(_loc2_,"bg",-5);
         _loc4_ = this.bg_mc.attachMovie(_loc2_,"bg",-10);
         _loc5_._x = 5;
         _loc5_._y = 5;
         _loc4_._x = 10;
         _loc4_._y = 10;
      }
   }
   function set toggled(b)
   {
      this.toggled_frame = b;
      this._toggled = b;
   }
   function set toggled_frame(b)
   {
      if(b)
      {
         this.bg_mc.bg.gotoAndStop(2);
         this.info_btn.gotoAndStop(2);
      }
      else
      {
         this.bg_mc.bg.gotoAndStop(1);
         this.info_btn.gotoAndStop(1);
      }
   }
   function get toggled()
   {
      return this._toggled;
   }
}
