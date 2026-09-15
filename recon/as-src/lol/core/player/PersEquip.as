class lol.core.player.PersEquip extends lol.core.player.StuffManager
{
   var XMC;
   var action_arr;
   var armor;
   var bag;
   var belt;
   var boots;
   var camouflage;
   var currUpdateSetItem;
   var dispatchEvent;
   var dropStack;
   var eatArr;
   var effect_manager;
   var head;
   var healArr;
   var id;
   var isGamer;
   var legs;
   var primary;
   var publicTrophy_arr;
   var secondary;
   var slots_arr;
   var sortMask;
   var thisPlayer;
   var transferStack;
   var tryLoading;
   var tryMode;
   var tryUnloading;
   var wear_arr;
   var first = false;
   function PersEquip(ID, em)
   {
      super();
      this.effect_manager = em;
      this.id = ID;
      this.isGamer = this.id == lol.core.player.Gamer.ID;
      this.thisPlayer = lol.core.Master.getInstance().getPlayer(this.id);
      this.XMC = lol.server.XMLConnection.getInstance();
      this.bag = new lol.core.player.Bag("bag");
      this.bag.maskIndex = 8;
      this.bag.index = 0;
      this.primary = new lol.core.player.Slot("primary","hand","hand");
      this.primary.maskIndex = 2;
      this.primary.index = 0;
      this.primary.addEventListener("changeSlot",this);
      this.secondary = new lol.core.player.Slot("secondary","hand","hand");
      this.secondary.maskIndex = 2;
      this.secondary.index = 1;
      this.head = new lol.core.player.Slot("head","head","wear");
      this.head.maskIndex = 1;
      this.head.index = 0;
      this.camouflage = new lol.core.player.Slot("camouflage","camouflage","wear");
      this.camouflage.maskIndex = 1;
      this.camouflage.index = 1;
      this.armor = new lol.core.player.Slot("armor","armor","wear");
      this.armor.maskIndex = 1;
      this.armor.index = 2;
      this.belt = new lol.core.player.Slot("belt","belt","wear");
      this.belt.maskIndex = 1;
      this.belt.index = 3;
      this.legs = new lol.core.player.Slot("legs","legs","wear");
      this.legs.maskIndex = 1;
      this.legs.index = 4;
      this.boots = new lol.core.player.Slot("boots","boots","wear");
      this.boots.maskIndex = 1;
      this.boots.index = 5;
      this.slots_arr = [this.head,this.camouflage,this.armor,this.belt,this.legs,this.boots];
      this.action_arr = [this.primary,this.secondary];
      this.sortMask = lol.gpui.UserSettings.getSetting("sortMask","equip");
      if(this.sortMask == undefined)
      {
         this.sortMask = [1,1,1,1,1,1];
      }
      this.createHealArr();
   }
   function get primaryItem()
   {
      var _loc3_ = this.primary.item;
      if(_loc3_)
      {
         return _loc3_;
      }
      var _loc2_ = new lol.core.objects.MeleeWeapon(0,0,lol.core.objects.Item.FIST);
      _loc2_.weapon_type = 0;
      _loc2_.strikeCost = 5;
      _loc2_.inited = true;
      _loc2_._name = "кулак";
      _loc2_._animation_type = "fist";
      return _loc2_;
   }
   function set primaryItem(_item)
   {
      this.primary.item = _item;
   }
   function get secondaryItem()
   {
      var _loc2_ = this.secondary.item;
      return _loc2_;
   }
   function firstRequest()
   {
      var _loc2_;
      if(!this.first)
      {
         this.first = true;
         _loc2_ = this.bag.maskIndex + this.primary.maskIndex + this.head.maskIndex;
         this.getStuff(_loc2_,this.id);
      }
   }
   function actionSlotsRequest()
   {
      var _loc2_ = this.primary.maskIndex;
   }
   function ss_ack(obj)
   {
      var _loc13_ = obj.param;
      var _loc4_ = obj.param.o_list;
      var _loc3_ = obj.data.toString(2);
      var _loc2_ = _loc3_.length - 1;
      var _loc7_ = _loc2_ < 0 ? 0 : Number(_loc3_.substr(_loc2_ - 0,1));
      var _loc10_ = _loc2_ < 1 ? 0 : Number(_loc3_.substr(_loc2_ - 1,1));
      var _loc9_ = _loc2_ < 2 ? 0 : Number(_loc3_.substr(_loc2_ - 2,1));
      var _loc11_ = _loc2_ < 3 ? 0 : Number(_loc3_.substr(_loc2_ - 3,1));
      var _loc12_ = _loc2_ < 4 ? 0 : Number(_loc3_.substr(_loc2_ - 4,1));
      var _loc8_;
      if(_loc7_)
      {
         if(this.isGamer)
         {
            _loc8_ = _loc4_.splice(0,this.slots_arr.length);
            this.parseWear(_loc8_);
         }
         else
         {
            this.wear_arr = _loc4_.splice(0,this.slots_arr.length);
         }
      }
      if(_loc10_)
      {
         _loc8_ = _loc4_.splice(0,this.action_arr.length);
         this.parseAction(_loc8_);
      }
      if(!_loc9_)
      {
      }
      if(!_loc12_)
      {
      }
      if(_loc11_)
      {
         this.parseBag(_loc4_);
      }
      var _loc5_ = obj.param.set_res;
      if(_loc5_)
      {
         if(this.isGamer)
         {
            if(lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_OWN_WEAR_SET))
            {
               lol.core.Master.getInstance().getPlayer(this.id).playerInfo.setResID = _loc5_;
            }
            else
            {
               lol.core.Master.getInstance().getPlayer(this.id).playerInfo.setResID = null;
            }
         }
         else
         {
            lol.core.Master.getInstance().getPlayer(this.id).playerInfo.setResID = _loc5_;
         }
      }
      this.dispatchEvent({type:"changeOutfit"});
   }
   function parseWear(arr)
   {
      var _loc6_ = !arr ? this.wear_arr : arr;
      var _loc2_ = 0;
      var _loc3_;
      var _loc5_;
      var _loc4_;
      while(_loc2_ < this.slots_arr.length)
      {
         _loc3_ = _loc6_[_loc2_];
         _loc5_ = this.createItem(_loc3_,!this.isGamer);
         _loc4_ = this.slots_arr[_loc2_];
         this.addItem(_loc4_,_loc5_);
         _loc2_ = _loc2_ + 1;
      }
   }
   function parseAction(arr)
   {
      var _loc2_ = 0;
      var _loc3_;
      var _loc5_;
      var _loc4_;
      while(_loc2_ < this.action_arr.length)
      {
         _loc3_ = arr[_loc2_];
         _loc5_ = this.createItem(_loc3_,!this.isGamer);
         _loc4_ = this.action_arr[_loc2_];
         this.addItem(_loc4_,_loc5_);
         _loc2_ = _loc2_ + 1;
      }
   }
   function parseBag(arr)
   {
      var _loc2_ = 0;
      var _loc3_;
      var _loc4_;
      while(_loc2_ < arr.length)
      {
         _loc3_ = arr[_loc2_];
         _loc4_ = this.createItem(_loc3_,!this.isGamer);
         this.addItem(this.bag,_loc4_);
         _loc2_ = _loc2_ + 1;
      }
   }
   function addItem(slot, item, i, check_set)
   {
      super.addItem(slot,item,i);
      if(item instanceof lol.core.objects.HealItem)
      {
         this.addHealItem(item);
      }
      if(check_set == true || check_set == undefined)
      {
         this.checkFullSet();
      }
   }
   function removeItem(slot, item)
   {
      if(item instanceof lol.core.objects.HealItem)
      {
         this.removeHealItem(item);
      }
      super.removeItem(slot,item);
      this.checkFullSet();
   }
   function __addItem(item)
   {
      if(!item.inited)
      {
         item.addEventListener("itemUpdate",this);
      }
      else
      {
         this.addItem(this.bag,item);
      }
   }
   function itemUpdate(obj)
   {
      var _loc2_ = obj.target;
      this.addItem(this.bag,_loc2_);
   }
   function ss_obj_status(obj)
   {
      var _loc3_ = obj.param.obj;
      var _loc5_ = obj.param.status;
      var _loc2_;
      var _loc4_;
      var _loc6_;
      if(_loc5_ == 0)
      {
         _loc2_ = this.findItem(_loc3_);
         if(_loc2_.item && _loc2_.slot)
         {
            this.removeItem(_loc2_.slot,_loc2_.item);
            if(_loc2_.item instanceof lol.core.objects.HealItem)
            {
               this.dispatchEvent(new lol.events.TimeBarEvent(lol.events.TimeBarEvent.END_HEAL));
            }
            if(_loc2_.slot == this.primary || _loc2_.slot == this.secondary)
            {
               if(_loc2_.item.rootID == lol.core.objects.Item.HEAL_ITEM)
               {
                  _loc4_ = this.bag.getItemsByType(_loc2_.item.typeID)[0];
                  if(_loc4_)
                  {
                     this.transferItem(_loc4_,this.bag,_loc2_.slot);
                  }
               }
            }
         }
      }
      else if(_loc5_ == 1)
      {
         _loc6_ = this.createItem(_loc3_);
         this.addItem(this.bag,_loc6_);
      }
   }
   function checkRemove(slot, oID)
   {
   }
   function findItem(oid)
   {
      var _loc3_ = this.bag.getItem(oid);
      if(_loc3_)
      {
         return {item:_loc3_,slot:this.bag};
      }
      if(this.primary.item.oID == oid)
      {
         _loc3_ = this.primary.item;
         return {item:_loc3_,slot:this.primary};
      }
      if(this.secondary.item.oID == oid)
      {
         _loc3_ = this.secondary.item;
         return {item:_loc3_,slot:this.secondary};
      }
      var _loc2_;
      for(var _loc5_ in this.slots_arr)
      {
         _loc2_ = this.slots_arr[_loc5_];
         if(_loc2_.item.oID == oid)
         {
            _loc3_ = _loc2_.item;
            return {item:_loc3_,slot:_loc2_};
         }
      }
   }
   function requestTranfer(transferObj)
   {
      var _loc6_;
      var _loc3_;
      var _loc4_;
      var _loc5_;
      if(this.checkTransfer(transferObj))
      {
         _loc6_ = transferObj.from.maskIndex << 8 | transferObj.from.index;
         _loc3_ = transferObj.to.maskIndex << 8 | transferObj.to.index;
         _loc4_ = transferObj.item.id;
         _loc5_ = new lol.server.mess.CSM_SSMove(_loc6_,_loc3_,new lol.data.BigUINT(new lol.data.BigUINTCluster(_loc4_)));
         if(this.XMC.Send(_loc5_))
         {
            lol.server.XMLCCallStack.addCall("cmdAck",this,this.transferAck);
         }
      }
      else
      {
         this.applyTransfer(false);
      }
   }
   function applyTransfer(succes)
   {
      var _loc2_ = this.transferStack.shift();
      var _loc3_;
      if(succes && _loc2_.to.item)
      {
         _loc3_ = _loc2_.to.item;
         this.removeItem(_loc2_.to,_loc3_);
      }
      this.__applyTransfer(succes,_loc2_);
      if(_loc3_)
      {
         this.addItem(_loc2_.from,_loc3_,_loc2_.fromPos);
      }
      if(succes)
      {
         this.dispatchEvent({type:lol.gpui.DDEvents.TRANSFER_SUCCESS});
      }
      else
      {
         this.dispatchEvent({type:lol.gpui.DDEvents.TRANSFER_ERROR});
      }
   }
   function checkUse(transferObj)
   {
      var _loc3_ = transferObj.item.getProp("actions");
      var _loc4_ = transferObj.hitted.getProp("action_map");
      if(transferObj.item instanceof lol.core.objects.Ammo && transferObj.hitted instanceof lol.core.objects.FireArm)
      {
         this.loadFireArm(lol.core.objects.FireArm(transferObj.hitted),lol.core.objects.Ammo(transferObj.item));
         this.removeItem(transferObj.from,transferObj.item);
         transferObj.to = null;
         this.applyTransfer(false);
         return true;
      }
      if(transferObj.item instanceof lol.core.objects.Heapable && transferObj.hitted instanceof lol.core.objects.Heapable)
      {
         if(transferObj.item.typeID == transferObj.hitted.typeID)
         {
            this.joinHeap(lol.core.objects.Heapable(transferObj.item),lol.core.objects.Heapable(transferObj.hitted));
            this.removeItem(transferObj.from,transferObj.item);
            transferObj.to = null;
            this.applyTransfer(false);
            return true;
         }
      }
      return false;
   }
   function changePrimary()
   {
      var _loc3_;
      var _loc2_;
      var _loc4_;
      if(this.secondary.item)
      {
         _loc3_ = this.secondary.item;
         _loc2_ = this.secondary;
         _loc4_ = this.primary;
      }
      else
      {
         _loc3_ = this.primary.item;
         _loc2_ = this.primary;
         _loc4_ = this.secondary;
      }
      this.transferItem(_loc3_,_loc2_,_loc4_);
   }
   function changeSlot(obj)
   {
      var _loc2_ = obj.target;
      var _loc3_ = _loc2_.item;
      if(_loc2_ == this.primary)
      {
         this.dispatchEvent({type:"changePrimary"});
      }
   }
   function loadFireArm(fireArm, ammo)
   {
      if(fireArm.compare(ammo))
      {
         this.tryLoading = {ammo:ammo,fireArm:fireArm};
         this.gamer.addEventListener("useAck",this,this.firearmLoaded);
         this.gamer.loadObject(fireArm,ammo);
      }
   }
   function firearmLoaded(obj)
   {
      this.gamer.removeEventListener("useAck",this,this.firearmLoaded);
      if(obj.res == 0)
      {
         this.tryLoading.fireArm.lastAmmo = this.tryLoading.ammo;
         this.dispatchEvent(new lol.events.TimeBarEvent(lol.events.TimeBarEvent.RELOAD,this.tryLoading.fireArm));
      }
      else
      {
         this.tryLoading = null;
      }
   }
   function reloadloadFireArm(fireArm)
   {
      var _loc9_;
      var _loc8_;
      var _loc2_;
      var _loc7_;
      var _loc6_;
      var _loc4_;
      var _loc3_;
      if(fireArm.lastAmmo && this.bag.getItem(fireArm.lastAmmo))
      {
         _loc9_ = this.bag.getItem(fireArm.lastAmmo);
         _loc8_ = lol.core.objects.Ammo(_loc9_);
         _loc2_ = _loc8_.getProp("premium");
         if(_loc2_ && _loc2_ > lol.core.Master.getInstance().gamer.premium)
         {
            if(_loc2_ == 1)
            {
               lol.utils.ErrorReport.callReport(0,1002);
            }
            else if(_loc2_ == 2)
            {
               lol.utils.ErrorReport.callReport(0,1003);
            }
         }
         else
         {
            this.loadFireArm(fireArm,_loc8_);
         }
      }
      else
      {
         _loc7_ = this.bag.getItems();
         _loc6_ = 0;
         _loc4_ = 0;
         while(_loc4_ < _loc7_.length)
         {
            _loc3_ = _loc7_[_loc4_];
            if(_loc3_ instanceof lol.core.objects.Ammo)
            {
               if(fireArm.compare(_loc3_))
               {
                  if(fireArm.ammoCount == 0 || _loc3_.typeID == fireArm.ammoType)
                  {
                     _loc2_ = _loc3_.getProp("premium");
                     if(_loc2_ == 0 || _loc2_ == undefined || isNaN(_loc2_) || _loc2_ <= lol.core.Master.getInstance().gamer.premium)
                     {
                        this.loadFireArm(fireArm,_loc3_);
                        _loc6_ = 0;
                        return undefined;
                     }
                     _loc6_ = _loc2_;
                  }
               }
            }
            _loc4_ = _loc4_ + 1;
         }
         if(_loc6_ > 0)
         {
            if(_loc6_ == 1)
            {
               lol.utils.ErrorReport.callReport(0,1002);
            }
            else if(_loc6_ == 2)
            {
               lol.utils.ErrorReport.callReport(0,1003);
            }
         }
      }
   }
   function unloadFireArm(fireArm)
   {
      this.tryUnloading = {fireArm:fireArm};
      this.gamer.addEventListener("useAck",this,this.firearmUnLoaded);
      this.gamer.unloadObject(fireArm);
   }
   function firearmUnLoaded(obj)
   {
      this.gamer.removeEventListener("useAck",this,this.firearmUnLoaded);
      if(obj.res == 0)
      {
         this.dispatchEvent(new lol.events.TimeBarEvent(lol.events.TimeBarEvent.UNLOAD,this.tryUnloading.fireArm));
      }
   }
   function loadPrimary()
   {
      var _loc2_ = this.primary.item;
      if(_loc2_ && _loc2_ instanceof lol.core.objects.FireArm)
      {
         this.reloadloadFireArm(_loc2_);
      }
   }
   function unloadPrimary()
   {
      var _loc2_ = this.primary.item;
      if(_loc2_)
      {
         this.unloadFireArm(_loc2_);
      }
   }
   function getAmmo(fireArm)
   {
      var _loc3_ = fireArm.getProp("comp_ammo");
      var _loc4_ = new Array();
      var _loc1_ = 0;
      var _loc2_;
      while(_loc1_ < _loc3_.length)
      {
         _loc2_ = lol.core.objects.ItemFactory.createPrototype(_loc3_[_loc1_],lol.core.objects.Item.AMMO);
         _loc4_.push(_loc2_);
         _loc1_ = _loc1_ + 1;
      }
      return _loc4_;
   }
   function getAmmoExist(fireArm)
   {
      var _loc6_ = new Array();
      var _loc4_ = fireArm.getProp("comp_ammo");
      var _loc3_;
      var _loc5_;
      var _loc2_ = 0;
      while(_loc2_ < _loc4_.length)
      {
         _loc5_ = _loc4_[_loc2_];
         _loc3_ = this.bag.getItemsByType(_loc5_);
         if(_loc3_.length > 0)
         {
            _loc6_.push(_loc3_[0]);
         }
         _loc2_ = _loc2_ + 1;
      }
      return _loc6_;
   }
   function getNumberOfExistAmmo(fireArm)
   {
      var _loc9_ = 0;
      var _loc6_ = new Array();
      var _loc7_ = fireArm.getProp("comp_ammo");
      var _loc3_;
      var _loc8_;
      var _loc5_ = 0;
      var _loc2_;
      var _loc4_;
      while(_loc5_ < _loc7_.length)
      {
         _loc8_ = _loc7_[_loc5_];
         _loc3_ = this.bag.getItemsByType(_loc8_);
         if(_loc3_.length > 0)
         {
            _loc2_ = 0;
            while(_loc2_ < _loc3_.length)
            {
               _loc4_ = _loc3_[_loc2_];
               _loc6_.push(_loc4_);
               _loc2_ = _loc2_ + 1;
            }
         }
         _loc5_ = _loc5_ + 1;
      }
      return _loc6_;
   }
   function changeFireMode(m)
   {
      var _loc3_ = this.primary.item;
      var _loc2_;
      var _loc4_;
      if(_loc3_ instanceof lol.core.objects.FireArm)
      {
         _loc2_ = lol.core.objects.FireArm(_loc3_);
         _loc4_ = _loc2_.getProp("fire_mods");
         if(_loc4_[m])
         {
            this.tryMode = m;
            this.gamer.addEventListener("useAck",this,this.applyChangeFireMode);
            this.gamer.changeUseMode(_loc2_,m);
         }
      }
   }
   function applyChangeFireMode(obj)
   {
      this.gamer.removeEventListener("useAck",this,this.applyChangeFireMode);
      var _loc2_ = lol.core.objects.FireArm(this.primary.item);
      if(obj.res == 0)
      {
         _loc2_.cur_mode = this.tryMode;
      }
      else
      {
         this.tryMode = _loc2_.cur_mode;
      }
      this.dispatchEvent({type:"changePrimary",changeFireMode:true});
   }
   function onDoubleClick(_item, _from)
   {
      var _loc3_;
      var _loc4_;
      var _loc2_;
      var _loc5_;
      if(_item)
      {
         _loc3_ = this.getSlot(_from);
         _loc4_ = _item;
         if(_loc3_ == this.bag)
         {
            _loc2_ = 3;
         }
         else if(_loc3_ == this.secondary)
         {
            _loc2_ = 1.5;
         }
         else
         {
            _loc2_ = 1;
         }
         _loc5_ = _loc4_.getProp("actions");
         if(_loc5_[1].enable)
         {
            this.gamer.itemActivator.setPenalty(_loc2_);
            this.useToYourSelf(_loc4_);
            this.applyTransfer(false);
         }
      }
   }
   function useToYourSelf(item)
   {
      if(item instanceof lol.core.objects.HealItem)
      {
         this.dispatchEvent(new lol.events.TimeBarEvent(lol.events.TimeBarEvent.HEAL,item));
      }
      this.gamer.useObjectIdle(item);
   }
   function dropItem(item, from)
   {
      var _loc3_ = this.getSlot(from.id);
      var _loc2_;
      if(!this.gamer.loot)
      {
         this.gamer.loot = new lol.core.player.Loot();
         _loc2_ = this.gamer.walker.numPos;
         this.gamer.loot.addEventListener("onLoot",this);
         this.gamer.loot.createSession(_loc2_,true);
      }
      if(this.gamer.loot.status)
      {
         this.gamer.loot.transferItem(item,this.bag,this.gamer.loot.lootBag);
      }
      else
      {
         if(!this.dropStack)
         {
            this.dropStack = new Array();
         }
         this.dropStack.push({item:item,from:_loc3_});
      }
   }
   function onLoot(obj)
   {
      var _loc2_;
      var _loc4_;
      var _loc3_;
      while(this.dropStack.length > 0)
      {
         _loc2_ = this.dropStack.shift();
         _loc4_ = _loc2_.item;
         _loc3_ = _loc2_.from;
         this.gamer.loot.transferItem(_loc4_,_loc3_,this.gamer.loot.lootBag);
      }
   }
   function close()
   {
      if(this.gamer.loot)
      {
         this.dropStack = null;
         this.gamer.loot.removeEventListener("onLoot",this);
         this.gamer.loot.close();
      }
   }
   function get gamer()
   {
      return lol.core.Master.getInstance().gamer;
   }
   function getBreakedItems()
   {
      var _loc6_ = new Array();
      var _loc2_;
      var _loc5_ = this.slots_arr.length;
      var _loc4_;
      var _loc3_;
      _loc2_ = 0;
      var _loc7_;
      while(_loc2_ < _loc5_)
      {
         _loc7_ = this.slots_arr[_loc2_];
         _loc4_ = _loc7_.item;
         if(_loc4_ instanceof lol.core.objects.Breakable)
         {
            _loc3_ = lol.core.objects.Breakable(_loc4_);
            if(_loc3_.getCurQuality() < 1)
            {
               _loc6_.push(_loc3_);
            }
         }
         _loc2_ = _loc2_ + 1;
      }
      _loc5_ = this.action_arr.length;
      _loc2_ = 0;
      while(_loc2_ < _loc5_)
      {
         _loc7_ = this.action_arr[_loc2_];
         _loc4_ = _loc7_.item;
         if(_loc4_ instanceof lol.core.objects.Breakable)
         {
            _loc3_ = lol.core.objects.Breakable(_loc4_);
            if(_loc3_.getCurQuality() < 1)
            {
               _loc6_.push(_loc3_);
            }
         }
         _loc2_ = _loc2_ + 1;
      }
      _loc5_ = this.bag.itemList.length;
      _loc2_ = 0;
      while(_loc2_ < _loc5_)
      {
         _loc4_ = this.bag.itemList[_loc2_];
         if(_loc4_ instanceof lol.core.objects.Breakable)
         {
            _loc3_ = lol.core.objects.Breakable(_loc4_);
            if(_loc3_.getCurQuality() < 1)
            {
               _loc6_.push(_loc3_);
            }
         }
         _loc2_ = _loc2_ + 1;
      }
      return _loc6_;
   }
   function ss_obj_move(obj)
   {
      var _loc7_ = obj.param.from;
      var _loc5_ = obj.param.to;
      var _loc9_ = _loc7_ >> 8;
      var _loc6_ = _loc5_ >> 8;
      var _loc11_ = _loc7_ & 0xFF;
      var _loc3_ = _loc5_ & 0xFF;
      var _loc8_;
      var _loc14_;
      var _loc13_;
      if(_loc9_ == 1)
      {
         _loc8_ = obj.param.obj;
         _loc14_ = this.createItem(_loc8_,!this.isGamer);
         _loc13_ = this.slots_arr[_loc11_];
         this.removeItem(_loc13_,_loc14_);
      }
      var _loc4_;
      var _loc10_;
      var _loc15_;
      var _loc12_;
      if(_loc6_ == this.primary.maskIndex && _loc3_ == this.primary.index)
      {
         _loc8_ = obj.param.obj;
         _loc4_ = lol.utils.MDString.parseBigUINT(_loc8_,4,2);
         _loc10_ = _loc4_[0];
         _loc15_ = _loc4_[1];
         _loc12_ = lol.core.objects.ItemFactory.createPrototype(_loc15_,_loc10_);
         this.primaryItem = _loc12_.item;
      }
      else if(_loc6_ == 1)
      {
         _loc8_ = obj.param.obj;
         _loc14_ = this.createItem(_loc8_,!this.isGamer);
         _loc13_ = this.slots_arr[_loc3_];
         this.addItem(_loc13_,_loc14_);
      }
   }
   function getEffects(healItem)
   {
      var _loc4_ = healItem.getProp("_effects");
      var _loc5_ = new Array();
      var _loc2_ = 0;
      var _loc3_;
      while(_loc2_ < _loc4_.length)
      {
         _loc3_ = lol.core.effects.EffectsFactory.createProtoEffect(this.effect_manager,_loc4_[_loc2_]);
         _loc5_.push(_loc3_);
         _loc2_ = _loc2_ + 1;
      }
      return _loc5_;
   }
   function createHealArr()
   {
      this.healArr = new Array();
      this.eatArr = new Array();
      var _loc2_ = this.bag.itemList;
      var _loc5_;
      var _loc6_;
      var _loc7_;
      for(var _loc4_ in _loc2_)
      {
         _loc5_ = _loc2_[_loc4_];
         if(_loc5_ instanceof lol.core.objects.HealItem)
         {
            if(_loc5_.inited)
            {
               _loc6_ = _loc5_.getProp("max_h_rest");
               _loc7_ = _loc5_.getProp("max_st_rest");
               if(_loc6_)
               {
                  this.healArr.push({item:_loc5_,max_h_rest:Number(_loc6_)});
               }
               if(_loc7_)
               {
                  this.eatArr.push({item:_loc5_,max_st_rest:Number(_loc7_)});
               }
               this.dispatchEvent({type:"updateHealItem"});
               this.dispatchEvent({type:"updateEatItem"});
            }
            else
            {
               _loc5_.addEventListener("itemUpdate",this,this.hItemUpdate);
            }
         }
      }
      if(this.primaryItem instanceof lol.core.objects.HealItem)
      {
         _loc6_ = this.primaryItem.getProp("max_h_rest");
         _loc7_ = this.primaryItem.getProp("max_st_rest");
         if(_loc6_)
         {
            this.healArr.push({item:this.primaryItem,max_h_rest:Number(_loc6_)});
         }
         if(_loc7_)
         {
            this.eatArr.push({item:this.primaryItem,max_st_rest:Number(_loc7_)});
         }
      }
      if(this.secondaryItem instanceof lol.core.objects.HealItem)
      {
         _loc6_ = this.secondaryItem.getProp("max_h_rest");
         _loc7_ = this.secondaryItem.getProp("max_st_rest");
         if(_loc6_)
         {
            this.healArr.push({item:this.secondaryItem,max_h_rest:Number(_loc6_)});
         }
         if(_loc7_)
         {
            this.eatArr.push({item:this.secondaryItem,max_st_rest:Number(_loc7_)});
         }
      }
      this.healArr.sortOn("max_h_rest",Array.NUMERIC);
      this.eatArr.sortOn("max_st_rest",Array.NUMERIC);
   }
   function hItemUpdate(obj)
   {
      obj.target.removeEventListener("itemUpdate",this,this.hItemUpdate);
      this.addHealItem(obj.target);
   }
   function addHealItem(item)
   {
      var _loc3_;
      var _loc4_;
      if(item.inited)
      {
         _loc3_ = item.getProp("max_h_rest");
         _loc4_ = item.getProp("max_st_rest");
         if(_loc3_)
         {
            this.healArr.push({item:item,max_h_rest:Number(_loc3_)});
            this.healArr.sortOn("max_h_rest",Array.NUMERIC);
            this.dispatchEvent({type:"updateHealItem"});
         }
         if(_loc4_)
         {
            this.eatArr.push({item:item,max_st_rest:Number(_loc4_)});
            this.eatArr.sortOn("max_st_rest");
            this.dispatchEvent({type:"updateEatItem"});
         }
         this.healArr.sortOn("max_h_rest",Array.NUMERIC);
      }
      else
      {
         item.addEventListener("itemUpdate",this,this.hItemUpdate);
      }
   }
   function removeHealItem(item)
   {
      var _loc4_ = item.getProp("max_h_rest");
      var _loc5_ = item.getProp("max_st_rest");
      if(_loc4_)
      {
         for(var _loc3_ in this.healArr)
         {
            if(this.healArr[_loc3_].item == item)
            {
               this.healArr.splice(Number(_loc3_),1);
            }
         }
      }
      if(_loc5_)
      {
         for(_loc3_ in this.eatArr)
         {
            if(this.eatArr[_loc3_].item == item)
            {
               this.eatArr.splice(Number(_loc3_),1);
            }
         }
      }
   }
   function useHealItem()
   {
      var _loc6_;
      var _loc2_;
      var _loc3_;
      var _loc4_;
      var _loc5_;
      if(lol.core.Master.getInstance().currentLocation.warStatus)
      {
         _loc2_ = this.healArr.length - 1;
         while(_loc2_ >= 0)
         {
            _loc3_ = this.healArr[_loc2_].item;
            _loc4_ = _loc3_.getProp("heal_cost");
            _loc5_ = lol.core.Master.getInstance().gamer.apManager.maxAP;
            if(_loc4_ <= _loc5_)
            {
               _loc6_ = lol.core.objects.HealItem(_loc3_);
               break;
            }
            _loc2_ = _loc2_ - 1;
         }
      }
      else
      {
         _loc6_ = this.healArr[this.healArr.length - 1].item;
      }
      if(_loc6_)
      {
         lol.core.Master.getInstance().gamer.useObjectIdle(_loc6_);
         this.dispatchEvent(new lol.events.TimeBarEvent(lol.events.TimeBarEvent.HEAL,_loc6_));
      }
   }
   function useEatItem()
   {
      var _loc6_;
      var _loc2_;
      var _loc3_;
      var _loc4_;
      var _loc5_;
      if(lol.core.Master.getInstance().currentLocation.warStatus)
      {
         _loc2_ = this.eatArr.length - 1;
         while(_loc2_ >= 0)
         {
            _loc3_ = this.eatArr[_loc2_].item;
            _loc4_ = _loc3_.getProp("heal_cost");
            _loc5_ = lol.core.Master.getInstance().gamer.apManager.maxAP;
            if(_loc4_ <= _loc5_)
            {
               _loc6_ = lol.core.objects.HealItem(_loc3_);
               break;
            }
            _loc2_ = _loc2_ - 1;
         }
      }
      else
      {
         _loc6_ = this.eatArr[this.eatArr.length - 1].item;
      }
      if(_loc6_)
      {
         lol.core.Master.getInstance().gamer.useObjectIdle(_loc6_);
         this.dispatchEvent(new lol.events.TimeBarEvent(lol.events.TimeBarEvent.HEAL,_loc6_));
      }
   }
   function getNumOfSetItem(typeID)
   {
      var _loc2_ = 0;
      if(this.head.item.getProp("setTypeID") == typeID && this.head.item.getProp("__break") > 0)
      {
         _loc2_ = _loc2_ + 1;
      }
      if(this.armor.item.getProp("setTypeID") == typeID && this.armor.item.getProp("__break") > 0)
      {
         _loc2_ = _loc2_ + 1;
      }
      if(this.camouflage.item.getProp("setTypeID") == typeID && this.camouflage.item.getProp("__break") > 0)
      {
         _loc2_ = _loc2_ + 1;
      }
      if(this.legs.item.getProp("setTypeID") == typeID && this.legs.item.getProp("__break") > 0)
      {
         _loc2_ = _loc2_ + 1;
      }
      if(this.boots.item.getProp("setTypeID") == typeID && this.boots.item.getProp("__break") > 0)
      {
         _loc2_ = _loc2_ + 1;
      }
      return _loc2_;
   }
   function getFullSetID()
   {
      var _loc2_;
      if(this.head.item.inited)
      {
         _loc2_ = this.head.item.getProp("setTypeID");
         if(this.armor.item.inited)
         {
            if(this.armor.item.getProp("setTypeID") != _loc2_)
            {
               return null;
            }
            if(this.camouflage.item.inited)
            {
               if(this.camouflage.item.getProp("setTypeID") != _loc2_)
               {
                  return null;
               }
               if(this.legs.item.inited)
               {
                  if(this.legs.item.getProp("setTypeID") != _loc2_)
                  {
                     return null;
                  }
                  if(this.boots.item.inited)
                  {
                     if(this.boots.item.getProp("setTypeID") != _loc2_)
                     {
                        return null;
                     }
                     return _loc2_;
                  }
                  if(this.boots.item)
                  {
                     this.currUpdateSetItem = this.boots.item;
                     this.currUpdateSetItem.addEventListener("itemUpdate",this,this.checkFullSet);
                     return null;
                  }
                  return null;
               }
               if(this.legs.item)
               {
                  this.currUpdateSetItem = this.legs.item;
                  this.currUpdateSetItem.addEventListener("itemUpdate",this,this.checkFullSet);
                  return null;
               }
               return null;
            }
            if(this.camouflage.item)
            {
               this.currUpdateSetItem = this.camouflage.item;
               this.currUpdateSetItem.addEventListener("itemUpdate",this,this.checkFullSet);
               return null;
            }
            return null;
         }
         if(this.armor.item)
         {
            this.currUpdateSetItem = this.armor.item;
            this.currUpdateSetItem.addEventListener("itemUpdate",this,this.checkFullSet);
            return null;
         }
         return null;
      }
      if(this.head.item)
      {
         this.currUpdateSetItem = this.head.item;
         this.currUpdateSetItem.addEventListener("itemUpdate",this,this.checkFullSet);
         return null;
      }
      return null;
   }
   function checkFullSetManually()
   {
      this.checkFullSet();
      this.dispatchEvent({type:"changeOutfit"});
   }
   function checkFullSet()
   {
      this.currUpdateSetItem.removeEventListener("itemUpdate",this,this.checkFullSet);
      var _loc4_;
      var _loc3_;
      var _loc2_;
      if(this.getFullSetID())
      {
         _loc4_ = this.getFullSetID();
         _loc3_ = lol.core.sets.SetManager.getSet(_loc4_);
         _loc3_.removeEventListener(lol.core.sets.SetObject.UPDATE_SET,this,this.checkFullSet);
         if(_loc3_.inited)
         {
            _loc2_ = lol.core.sets.SetManager.getSet(_loc4_).getProp("res");
            if(_loc2_)
            {
               if(this.isGamer)
               {
                  if(lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_OWN_WEAR_SET))
                  {
                     lol.core.Master.getInstance().getPlayer(this.id).playerInfo.setResID = _loc2_;
                  }
                  else
                  {
                     lol.core.Master.getInstance().getPlayer(this.id).playerInfo.setResID = null;
                  }
               }
               else
               {
                  lol.core.Master.getInstance().getPlayer(this.id).playerInfo.setResID = _loc2_;
               }
            }
         }
         else
         {
            _loc3_.addEventListener(lol.core.sets.SetObject.UPDATE_SET,this,this.checkFullSet);
         }
      }
      else
      {
         lol.core.Master.getInstance().getPlayer(this.id).playerInfo.setResID = null;
      }
   }
   function hasHealItem()
   {
      if(this.findHealItem())
      {
         return true;
      }
      return false;
   }
   function hasEatItem()
   {
      if(this.findEatItem())
      {
         return true;
      }
      return false;
   }
   function findAndUseHealItem()
   {
      var _loc2_ = this.findHealItem();
      if(_loc2_)
      {
         lol.core.Master.getInstance().gamer.useObjectIdle(_loc2_);
         this.dispatchEvent(new lol.events.TimeBarEvent(lol.events.TimeBarEvent.HEAL,_loc2_));
      }
   }
   function findAndUseEatItem()
   {
      var _loc2_ = this.findEatItem();
      if(_loc2_)
      {
         lol.core.Master.getInstance().gamer.useObjectIdle(_loc2_);
         this.dispatchEvent(new lol.events.TimeBarEvent(lol.events.TimeBarEvent.HEAL,_loc2_));
      }
   }
   function findHealItem()
   {
      var _loc9_ = this.primary.item.getProp("isHeal");
      var _loc7_ = this.primary.item.getProp("isBuff");
      var _loc8_ = this.secondary.item.getProp("isHeal");
      var _loc10_ = this.secondary.item.getProp("isBuff");
      if(this.primary.item instanceof lol.core.objects.HealItem && _loc9_ && !_loc7_)
      {
         return lol.core.objects.HealItem(this.primary.item);
      }
      if(this.secondary.item instanceof lol.core.objects.HealItem && _loc8_ && !_loc7_)
      {
         return lol.core.objects.HealItem(this.secondary.item);
      }
      var _loc6_ = this.bag.getItemsByRoot(lol.core.objects.Item.HEAL_ITEM);
      var _loc3_ = 0;
      var _loc2_;
      var _loc4_;
      var _loc5_;
      while(_loc3_ < _loc6_.length)
      {
         _loc2_ = lol.core.objects.HealItem(_loc6_[_loc3_]);
         _loc4_ = _loc2_.getProp("isHeal");
         _loc5_ = _loc2_.getProp("isBuff");
         if(_loc4_ && !_loc5_)
         {
            return _loc2_;
         }
         if(_loc4_ == undefined || _loc5_ == undefined)
         {
            _loc2_.addEventListener("itemUpdate",this,this.updateHealItem);
         }
         _loc3_ = _loc3_ + 1;
      }
   }
   function findEatItem()
   {
      var _loc10_ = this.primary.item.getProp("isHeal");
      var _loc9_ = this.primary.item.getProp("isBuff");
      var _loc7_ = this.secondary.item.getProp("isHeal");
      var _loc8_ = this.secondary.item.getProp("isBuff");
      if(this.primary.item instanceof lol.core.objects.HealItem && !_loc10_ && !_loc9_)
      {
         return lol.core.objects.HealItem(this.primary.item);
      }
      if(this.secondary.item instanceof lol.core.objects.HealItem && !_loc7_ && !_loc8_)
      {
         return lol.core.objects.HealItem(this.secondary.item);
      }
      var _loc6_ = this.bag.getItemsByRoot(lol.core.objects.Item.HEAL_ITEM);
      var _loc4_ = 0;
      var _loc2_;
      var _loc3_;
      var _loc5_;
      while(_loc4_ < _loc6_.length)
      {
         _loc2_ = lol.core.objects.HealItem(_loc6_[_loc4_]);
         _loc3_ = _loc2_.getProp("isHeal");
         _loc5_ = _loc2_.getProp("isBuff");
         if(!_loc3_ && _loc3_ != undefined && !_loc5_ && _loc5_ != undefined)
         {
            return _loc2_;
         }
         if(_loc3_ == undefined || _loc5_ == undefined)
         {
            _loc2_.addEventListener("itemUpdate",this,this.updateEatItem);
         }
         _loc4_ = _loc4_ + 1;
      }
   }
   function updateHealItem(obj)
   {
      obj.target.removeEventListener("itemUpdate",this,this.updateHealItem);
      this.dispatchEvent({type:"updateHealItem"});
   }
   function updateEatItem(obj)
   {
      obj.target.removeEventListener("itemUpdate",this,this.updateEatItem);
      this.dispatchEvent({type:"updateEatItem"});
   }
   function requestPublicTrophy()
   {
      var _loc2_ = 32;
      var _loc3_ = new lol.server.mess.CSM_SSGet(_loc2_,this.id);
      if(this.XMC.Send(_loc3_))
      {
         lol.server.XMLCCallStack.addCall("ss_ack",this,this.requestPublicTrophyAck);
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.requestPublicTrophyCMDAck);
      }
   }
   function requestPublicTrophyCMDAck(obj)
   {
      lol.server.XMLCCallStack.skipCall("ss_ack",this,this.requestPublicTrophyAck);
      this.dispatchEvent({type:"requestPublicTrophy"});
   }
   function requestPublicTrophyAck(obj)
   {
      lol.server.XMLCCallStack.skipCall("cmdAck",this,this.requestPublicTrophyCMDAck);
      var _loc7_ = obj.param;
      var _loc5_ = obj.param.o_list;
      this.publicTrophy_arr = new Array();
      var _loc2_ = 0;
      var _loc3_;
      var _loc4_;
      while(_loc2_ < _loc5_.length)
      {
         _loc3_ = _loc5_[_loc2_];
         if(this.isGamer)
         {
            _loc4_ = this.createItem(_loc3_);
         }
         else
         {
            _loc4_ = this.createItem(_loc3_,false,this.id);
         }
         this.publicTrophy_arr[_loc2_] = _loc4_;
         _loc2_ = _loc2_ + 1;
      }
      this.dispatchEvent({type:"requestPublicTrophy"});
   }
   function kill()
   {
      this.XMC.removeEventListener("ss_obj_status",this);
      this.gamer.loot.removeEventListener("onLoot",this);
      this.primary.removeEventListener("changeSlot",this);
      super.kill();
   }
   function getAllMyItems()
   {
      this.getStuff(31);
   }
}
