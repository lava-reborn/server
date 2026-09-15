class lol.core.objects.ItemActivator
{
   var XMC;
   var __usedItem;
   var breakInterval;
   var dispatchEvent;
   var gamer;
   var useFireArm;
   var useType;
   var autoReload_bool = true;
   var coolDownBlock = false;
   var penaltyAP = 1;
   function ItemActivator(_gamer)
   {
      this.gamer = _gamer;
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener("faShot",this,this.useFirearmAck);
      this.XMC.addEventListener("caHit",this,this.useMeleeAck);
      this.XMC.addEventListener("caMiss",this,this.useMeleeAck);
      this.XMC.addEventListener("breakMv",this,this.breackMove);
      this.XMC.addEventListener("lch",this,this.deadStateHandler);
      this.XMC.addEventListener("lcall",this,this.breakAction);
      lol.events.LEventDispatcher.initialize(this);
   }
   function deleteObject(item)
   {
      var _loc4_ = lol.core.objects.Item.DELETE;
      var _loc2_ = new lol.data.BigUINT(new lol.data.BigUINTCluster(item.oID));
      var _loc3_ = new lol.server.mess.CSM_SSUse(_loc4_,_loc2_);
      if(this.XMC.Send(_loc3_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.deleteAck);
      }
   }
   function deleteAck(obj)
   {
      var _loc2_ = obj.param.res;
      if(_loc2_ == 0)
      {
         this.dispatchEvent({type:lol.gpui.DDEvents.TRANSFER_SUCCESS});
      }
      else
      {
         this.dispatchEvent({type:lol.gpui.DDEvents.TRANSFER_ERROR});
      }
   }
   function loadObject(fireArm, ammo)
   {
      this.useType = lol.core.objects.Item.LOAD;
      var _loc2_ = fireArm.actions[this.useType].acID;
      this.useItem(_loc2_,fireArm.oID,ammo.oID);
   }
   function useObjectIdle(item)
   {
      this.useType = lol.core.objects.Item.USE_IDLE;
      var _loc2_ = item.actions[lol.core.objects.Item.USE_IDLE].acID;
      this.useItem(_loc2_,item.oID);
   }
   function useObjectToTarget(item, target)
   {
      this.useType = lol.core.objects.Item.USE_TARGET;
      var _loc3_ = item.actions[lol.core.objects.Item.USE_TARGET].acID;
      this.useItem(_loc3_,item.oID,target,item);
   }
   function useObjectToObject(item, target)
   {
      this.useType = lol.core.objects.Item.USE_ITEM;
      var _loc2_ = item.actions[lol.core.objects.Item.USE_ITEM].acID;
   }
   function fire(targetType, target)
   {
      var _loc6_;
      var _loc8_;
      var _loc3_;
      var _loc4_;
      var _loc2_;
      var _loc7_;
      if(lol.core.Master.getInstance().currentLocation.locInfo.battle)
      {
         if(targetType == 1 && lol.core.Master.getInstance().getPlayer(target) instanceof lol.core.player.Player && !lol.core.Master.getInstance().currentLocation.locInfo.pvpEnabled)
         {
            _loc6_ = lol.core.SceneShifter.openNewAlert("topSimple");
            _loc6_.label = "В этой локации Вы не можете нападать на других игроков";
            _loc8_ = new lol.utils.Timeout(lol.core.SceneShifter,lol.core.SceneShifter.closeAlert,2000,"topQuery");
         }
         else
         {
            this.useType = lol.core.objects.Item.FIRE;
            _loc3_ = lol.utils.MDString.createBigUINT([targetType,1],[target,8]);
            _loc4_ = this.gamer.equipment.primaryItem;
            _loc2_ = lol.core.objects.FireArm(_loc4_);
            if(_loc2_.ammo_count > 0)
            {
               _loc7_ = _loc2_.actions[lol.core.objects.Item.FIRE].acID;
               this.useItem(_loc7_,_loc2_.oID,_loc3_);
               this.dispatchEvent(new lol.events.TimeBarEvent(lol.events.TimeBarEvent.AIM));
            }
            else if(lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.AUTO_RELOAD))
            {
               this.gamer.equipment.loadPrimary();
               lol.utils.ErrorReport.callReport(0,13);
            }
            lol.core.Master.getInstance().gamer.acManager.setTargetID(target);
         }
      }
      else
      {
         _loc6_ = lol.core.SceneShifter.openNewAlert("topSimple");
         _loc6_.label = "В этой локации Вы не можете вести боевые действия";
         _loc8_ = new lol.utils.Timeout(lol.core.SceneShifter,lol.core.SceneShifter.closeAlert,2000,"topQuery");
      }
   }
   function strike(targetType, target)
   {
      var _loc6_;
      var _loc9_;
      var _loc3_;
      var _loc7_;
      var _loc2_;
      var _loc8_;
      var _loc4_;
      if(lol.core.Master.getInstance().currentLocation.locInfo.battle)
      {
         if(lol.core.Master.getInstance().getPlayer(target) instanceof lol.core.player.Player && !lol.core.Master.getInstance().currentLocation.locInfo.pvpEnabled)
         {
            _loc6_ = lol.core.SceneShifter.openNewAlert("topSimple");
            _loc6_.label = "В этой локации Вы не можете нападать на других игроков";
            _loc9_ = new lol.utils.Timeout(lol.core.SceneShifter,lol.core.SceneShifter.closeAlert,2000,"topQuery");
         }
         else
         {
            this.useType = lol.core.objects.Item.FIRE;
            _loc3_ = lol.utils.MDString.createBigUINT([targetType,1],[target,8]);
            _loc7_ = this.gamer.equipment.primaryItem;
            _loc2_ = lol.core.objects.MeleeWeapon(_loc7_);
            _loc8_ = 16;
            _loc4_ = !_loc2_ ? 0 : _loc2_.oID;
            this.useItem(_loc8_,_loc4_,_loc3_);
            lol.core.Master.getInstance().gamer.acManager.setTargetID(target);
            this.dispatchEvent(new lol.events.TimeBarEvent(lol.events.TimeBarEvent.STRIKE));
         }
      }
      else
      {
         _loc6_ = lol.core.SceneShifter.openNewAlert("topSimple");
         _loc6_.label = "В этой локации Вы не можете вести боевые действия";
         _loc9_ = new lol.utils.Timeout(lol.core.SceneShifter,lol.core.SceneShifter.closeAlert,2000,"topQuery");
      }
   }
   function unloadObject(fireArm)
   {
      this.useType = lol.core.objects.Item.UNLOAD;
      var _loc2_ = fireArm.actions[lol.core.objects.Item.UNLOAD].acID;
      this.useItem(_loc2_,fireArm.oID);
   }
   function changeUseMode(fireArm, mode)
   {
      this.useType = lol.core.objects.Item.USEMODE;
      var _loc4_ = mode.toString(16).length;
      var _loc3_ = "";
      var _loc2_ = 0;
      while(_loc2_ < 8 - _loc4_)
      {
         _loc3_ += "0";
         _loc2_ = _loc2_ + 1;
      }
      var _loc8_ = _loc3_ + mode.toString(16);
      var _loc6_ = fireArm.actions[lol.core.objects.Item.USEMODE].acID;
      this.useItem(_loc6_,fireArm.oID,mode);
   }
   function useItem(type, obj, target)
   {
      this.__usedItem = lol.core.objects.ItemFactory.getItem(obj);
      if(!this.__usedItem)
      {
         this.__usedItem = this.gamer.equipment.primaryItem;
      }
      var _loc2_;
      var _loc3_;
      var _loc4_;
      if(this.canUse())
      {
         _loc2_ = new lol.data.BigUINT(new lol.data.BigUINTCluster(obj));
         if(target != undefined)
         {
            _loc3_ = new lol.data.BigUINT(new lol.data.BigUINTCluster(target));
         }
         _loc4_ = new lol.server.mess.CSM_SSUse(type,_loc2_,_loc3_);
         if(!this.coolDownBlock)
         {
            if(this.XMC.Send(_loc4_))
            {
               this.coolDownBlock = true;
               this.useFireArm = true;
               clearInterval(this.breakInterval);
               this.breakInterval = setInterval(this,"breakAction",3000);
               lol.server.XMLCCallStack.addCall("cmdAck",this,this.useAck);
            }
         }
      }
      else
      {
         lol.utils.ErrorReport.callReport(0,11);
      }
   }
   function useAck(obj)
   {
      var _loc2_ = obj.param.res;
      if(_loc2_ == 0)
      {
         if(this.useType != lol.core.objects.Item.FIRE)
         {
            this.breakAction();
            this.releaseAPCost();
         }
      }
      else
      {
         this.breakAction();
      }
      this.gamer.dispatchAck(_loc2_);
   }
   function useFirearmAck(obj)
   {
      if(!obj.param.id && obj.param.status && this.useFireArm)
      {
         this.breakAction();
         this.releaseAPCost();
      }
   }
   function useMeleeAck(obj)
   {
      if(!obj.param.id)
      {
         this.breakAction();
         this.releaseAPCost();
      }
   }
   function breackMove(obj)
   {
      if(!obj.param.id)
      {
         this.breakAction();
      }
   }
   function deadStateHandler(obj)
   {
      var _loc2_ = obj.param.dead;
      var _loc3_;
      if(_loc2_ != undefined)
      {
         _loc3_ = _loc2_;
         if(_loc3_ == lol.core.player.Gamer.ID)
         {
            this.breakAction();
         }
      }
   }
   function breakAction()
   {
      clearInterval(this.breakInterval);
      this.useFireArm = false;
      this.coolDownBlock = false;
   }
   function releaseAPCost()
   {
      var _loc2_ = this.__usedItem.getAP(this.useType);
      this.gamer.apManager.ap -= _loc2_ * this.penaltyAP;
      this.penaltyAP = 1;
   }
   function setPenalty(p)
   {
      this.penaltyAP = p;
   }
   function canUse()
   {
      var _loc5_ = this.gamer.equipment.primaryItem;
      var _loc4_ = _loc5_.getAP(this.useType);
      var _loc2_ = lol.core.Master.getInstance();
      var _loc3_ = _loc2_.currentLocation.warStatus;
      if(_loc3_)
      {
         if(this.gamer.apManager.ap >= _loc4_)
         {
            return true;
         }
         return false;
      }
      return true;
   }
   function kill()
   {
      lol.server.XMLCCallStack.skipCall("cmdAck",this,this.useAck);
      this.XMC.removeEventListener("faShot",this,this.useFirearmAck);
      this.XMC.removeEventListener("caHit",this,this.useMeleeAck);
      this.XMC.removeEventListener("caMiss",this,this.useMeleeAck);
      this.XMC.removeEventListener("breakMv",this,this.breackMove);
      this.XMC.removeEventListener("lch",this,this.deadStateHandler);
      this.XMC.removeEventListener("lcall",this,this.breakAction);
   }
}
