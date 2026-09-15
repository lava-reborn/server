class lol.gpui.WeightPan extends lol.gpui.GPUIObject
{
   var bonusWeight_txt;
   var curWeight;
   var equipment;
   var gramm;
   var kilo;
   var maxWeight;
   var maxWeight_txt;
   var premium_mc;
   function WeightPan()
   {
      super();
      this.maxWeight = 0;
      this.curWeight = 0;
      this.kilo.alignText = "right";
      this.kilo.attachText = "moneyChar";
      this.kilo.letterSpace = 1;
      this.gramm.alignText = "left";
      this.gramm.attachText = "weightFont";
      this.gramm.letterSpace = 5;
      var _loc3_ = lol.core.Master.getInstance();
      this.equipment = _loc3_.gamer.equipment;
      this.equipment.addEventListener("addItem",this,this.count);
      this.equipment.addEventListener("removeItem",this,this.count);
      this.doLater("count");
      this.premium_mc.useHandCursor = false;
      var _loc4_ = _loc3_.gamer.premium;
      var premiumStr;
      if(_loc4_ == 1)
      {
         premiumStr = "Бонус за вид на жительство";
      }
      else if(_loc4_ == 2)
      {
         premiumStr = "Бонус за гражданство";
      }
      this.premium_mc.onRollOver = function()
      {
         lol.gpui.HintManager.showHint(premiumStr);
      };
      this.premium_mc.onRollOut = this.premium_mc.onPress = function()
      {
         lol.gpui.HintManager.closeHint();
      };
   }
   function getMaxWeight()
   {
      return this.maxWeight;
   }
   function getCurWeight()
   {
      return this.curWeight;
   }
   function count()
   {
      var _loc18_ = lol.core.Master.getInstance().gamer.attributes.max_weight;
      if(_loc18_)
      {
         this.calcMaxWeight();
      }
      else
      {
         lol.core.Master.getInstance().gamer.attributes.addEventListener(lol.events.PlayerEvent.UPDATE_PARAMS,this,this.updateParam);
      }
      var _loc17_ = new TextFormat();
      _loc17_.bold = true;
      var _loc5_ = this.equipment.bag.itemList;
      var _loc3_ = 0;
      var _loc4_;
      var _loc2_;
      for(var _loc6_ in _loc5_)
      {
         _loc4_ = _loc5_[_loc6_];
         _loc2_ = _loc4_.getProp("weight");
         if(_loc2_)
         {
            _loc3_ += _loc2_;
         }
      }
      var _loc14_ = this.equipment.primaryItem.getProp("weight");
      var _loc12_ = this.equipment.secondary.item.getProp("weight");
      var _loc7_ = this.equipment.head.item.getProp("weight");
      var _loc11_ = this.equipment.armor.item.getProp("weight");
      var _loc13_ = this.equipment.camouflage.item.getProp("weight");
      var _loc8_ = this.equipment.legs.item.getProp("weight");
      var _loc10_ = this.equipment.boots.item.getProp("weight");
      var _loc9_ = this.equipment.belt.item.getProp("weight");
      if(_loc14_ != undefined && !isNaN(_loc14_))
      {
         _loc3_ += _loc14_;
      }
      if(_loc12_ != undefined && !isNaN(_loc12_))
      {
         _loc3_ += _loc12_;
      }
      if(_loc7_ != undefined && !isNaN(_loc7_))
      {
         _loc3_ += _loc7_;
      }
      if(_loc11_ != undefined && !isNaN(_loc11_))
      {
         _loc3_ += _loc11_;
      }
      if(_loc13_ != undefined && !isNaN(_loc13_))
      {
         _loc3_ += _loc13_;
      }
      if(_loc8_ != undefined && !isNaN(_loc8_))
      {
         _loc3_ += _loc8_;
      }
      if(_loc10_ != undefined && !isNaN(_loc10_))
      {
         _loc3_ += _loc10_;
      }
      if(_loc9_ != undefined && !isNaN(_loc9_))
      {
         _loc3_ += _loc9_;
      }
      this.curWeight = _loc3_;
      var _loc15_ = String(Math.floor(_loc3_ / 1000));
      var _loc16_ = String(_loc3_ % 1000);
      this.kilo.showValue(_loc15_,2);
      this.gramm.showValue(_loc16_,undefined,3);
   }
   function calcMaxWeight()
   {
      var _loc8_ = "";
      var _loc4_ = lol.core.Master.getInstance().gamer.premium;
      var _loc2_ = lol.core.Master.getInstance().gamer.attributes.max_weight;
      var _loc5_ = new TextFormat();
      _loc5_.bold = true;
      var _loc3_;
      var _loc6_;
      var _loc7_;
      if(_loc4_)
      {
         if(_loc4_ == 1)
         {
            _loc3_ = lol.core.GConstatns.premium_weight_bonus_1;
         }
         else
         {
            _loc3_ = lol.core.GConstatns.premium_weight_bonus_2;
         }
         _loc6_ = Math.round(_loc2_ * _loc3_ * 0.001 / (_loc3_ + 1));
         _loc7_ = _loc2_ * 0.001 - _loc6_;
         this.premium_mc.gotoAndStop(_loc4_ + 1);
         this.bonusWeight_txt.text = "+" + _loc6_ + " кг";
         this.maxWeight_txt.text = _loc7_ + " кг";
         this.maxWeight = _loc2_ + _loc6_;
      }
      else
      {
         this.maxWeight_txt.text = _loc2_ * 0.001 + " кг";
         this.maxWeight = _loc2_;
      }
      this.maxWeight_txt.setTextFormat(_loc5_);
      this.bonusWeight_txt.setTextFormat(_loc5_);
   }
   function updateParam(obj)
   {
      lol.core.Master.getInstance().gamer.attributes.removeEventListener(lol.events.PlayerEvent.UPDATE_PARAMS,this,this.updateParam);
      var _loc2_ = lol.core.Master.getInstance().gamer.attributes.max_weight;
      if(_loc2_)
      {
         this.calcMaxWeight();
      }
   }
}
