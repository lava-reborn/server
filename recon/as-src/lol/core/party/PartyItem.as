class lol.core.party.PartyItem extends lol.gpui.GPUIObject
{
   var _label;
   var dispatchEvent;
   var hBar;
   var leaderSign;
   var partyPlayerMenuBtn;
   var sBar;
   function PartyItem()
   {
      super();
      this.doLater("init");
   }
   function init()
   {
      this.partyPlayerMenuBtn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openPartyPlayerMenu);
   }
   function openPartyPlayerMenu()
   {
      this.dispatchEvent({type:"openPartyPlayerMenu"});
   }
   function set label(l)
   {
      this.doLater("setLabel",[l]);
   }
   function setLabel(l)
   {
      this._label.text = l;
      this._label.autoSize = false;
   }
   function get label()
   {
      return this._label;
   }
   function setLeader(leader)
   {
      var _loc2_ = !leader ? 1 : 2;
      this.leaderSign.gotoAndStop(_loc2_);
   }
   function showHealth(hpercent)
   {
      this.hBar.hbar._xscale = hpercent;
   }
   function showStamina(spercent)
   {
      this.sBar.sbar._xscale = spercent;
   }
   function setStyle(obj)
   {
   }
}
